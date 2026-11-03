"""PigSkin AI Studio - original desktop research dashboard (Flet 0.28.3)."""
import asyncio
import base64
from datetime import datetime
import json
import logging
import time
import flet as ft
from pathlib import Path
from controllers.session import refresh_session
from ui.logging_setup import configure_logging
from views.model_operations import build_model_view
from services.accounts import (
    account_count, authenticate, authenticate_otp, contact_exists,
    current_account, find_contact_for_password_reset, find_verified_contact,
    list_users, otp_schema_ready, register, register_unverified_email,
    reset_password, update_active, update_role,
)
from services.dataset_audit import audit_dataset
from services.experiment_metrics import METRIC_NAMES,load_experiment_metrics
from services.inference import (inspect_image,predict,model_ready,model_spec,
    model_status,prewarm_ai_worker,shutdown_ai_worker)
from services.store import authorized_image_path,case_summary,count_cases,delete,recent,save,update_case
from services.workflow import (
    admin_metrics,close_support_thread,create_support_thread,mark_result_seen,
    mark_support_thread_seen,reply_support_thread,review_expert_result,
    submit_expert_result,support_messages,support_threads,support_unread_count,
    unseen_result_count,
)
from services.otp import (
    OTPError, OTPMigrationRequiredError, OTPNotConfiguredError, OTPService,
    configured_provider, normalize_contact,
)
from views.auth import build_auth_view

PALETTES={
    'dark':{'BG':'#07111D','SIDEBAR':'#0B1725','PANEL':'#102235','INNER':'#0B1B2C',
        'BORDER':'#214057','CYAN':'#34D8EA','BLUE':'#4B91FF','TEAL':'#20CCAD',
        'AMBER':'#F2BA55','WHITE':'#EAF6FF','MUTED':'#84A6BC','RED':'#FF6F84',
        'BAR_BG':'#243C4B','HEADER_BG':'#091724','CHIP_BG':'#183445',
        'IMAGE_BG':'#06101B','STATUS_BG':'#2B2418','NAV_SELECTED':'#173753'},
    'light':{'BG':'#F2F6F8','SIDEBAR':'#E6EDF2','PANEL':'#FFFFFF','INNER':'#F7F9FB',
        'BORDER':'#CEDAE3','CYAN':'#007B88','BLUE':'#2563EB','TEAL':'#0F766E',
        'AMBER':'#925500','WHITE':'#172B3A','MUTED':'#536A7B','RED':'#B4233C',
        'BAR_BG':'#D7E1E8','HEADER_BG':'#EAF0F4','CHIP_BG':'#DCE8ED',
        'IMAGE_BG':'#E2EAF0','STATUS_BG':'#FFF1D6','NAV_SELECTED':'#D5E8EF'},
}
BG=PALETTES['dark']['BG']; SIDEBAR=PALETTES['dark']['SIDEBAR']
PANEL=PALETTES['dark']['PANEL']; INNER=PALETTES['dark']['INNER']
BORDER=PALETTES['dark']['BORDER']; CYAN=PALETTES['dark']['CYAN']
BLUE=PALETTES['dark']['BLUE']; TEAL=PALETTES['dark']['TEAL']
AMBER=PALETTES['dark']['AMBER']; WHITE=PALETTES['dark']['WHITE']
MUTED=PALETTES['dark']['MUTED']; RED=PALETTES['dark']['RED']
BAR_BG=PALETTES['dark']['BAR_BG']; HEADER_BG=PALETTES['dark']['HEADER_BG']
CHIP_BG=PALETTES['dark']['CHIP_BG']; IMAGE_BG=PALETTES['dark']['IMAGE_BG']
STATUS_BG=PALETTES['dark']['STATUS_BG']; NAV_SELECTED=PALETTES['dark']['NAV_SELECTED']
PAGES=[('Tổng quan',ft.Icons.DASHBOARD_ROUNDED),('Phân tích ảnh',ft.Icons.IMAGE_SEARCH_ROUNDED),
       ('Lịch sử',ft.Icons.HISTORY_ROUNDED),('Dataset',ft.Icons.STORAGE_ROUNDED),
       ('Huấn luyện',ft.Icons.QUERY_STATS_ROUNDED),('Mô hình AI',ft.Icons.PSYCHOLOGY_ROUNDED)]
ROLE_PAGES={
    'user':(0,1,2,7),
    'expert':(0,1,2,3,4,5,7),
    'admin':(0,3,4,5,6,7),
}

def label(text,size=13,color=MUTED,bold=False,**kw):
    return ft.Text(str(text),size=size,color=color,weight=ft.FontWeight.BOLD if bold else ft.FontWeight.NORMAL,**kw)

def block(children,padding=17,expand=None,**kw):
    return ft.Container(bgcolor=PANEL,border=ft.border.all(1,BORDER),border_radius=14,padding=padding,
        expand=expand,content=ft.Column(children,spacing=12),**kw)

def caption_head(title,sub=None,icon=None):
    return ft.Column([ft.Row(([ft.Icon(icon,color=CYAN,size=20)] if icon else [])+[label(title,17,WHITE,True)]),
                     *([label(sub,11)] if sub else [])],spacing=3)

def kpi(name,value,icon,color=CYAN,sub=''):
    return ft.Container(expand=1,bgcolor=PANEL,border=ft.border.all(1,BORDER),border_radius=12,padding=16,
         content=ft.Column([ft.Row([ft.Icon(icon,color=color,size=20),ft.Container(expand=True)]),
            label(name,12),label(value,28,WHITE,True),label(sub,10)],spacing=8))

def meter(name,value,color=CYAN,caption=''):
    return ft.Column([ft.Row([label(name,12,WHITE),ft.Container(expand=True),label(f'{value*100:.1f}%',12,color,True)]),
        ft.ProgressBar(value=value,color=color,bgcolor=BAR_BG,bar_height=9),label(caption,10)],spacing=7)

def apply_palette(name):
    global BG,SIDEBAR,PANEL,INNER,BORDER,CYAN,BLUE,TEAL,AMBER,WHITE,MUTED,RED
    global BAR_BG,HEADER_BG,CHIP_BG,IMAGE_BG,STATUS_BG,NAV_SELECTED
    palette=PALETTES[name]
    BG=palette['BG']; SIDEBAR=palette['SIDEBAR']; PANEL=palette['PANEL']; INNER=palette['INNER']
    BORDER=palette['BORDER']; CYAN=palette['CYAN']; BLUE=palette['BLUE']; TEAL=palette['TEAL']
    AMBER=palette['AMBER']; WHITE=palette['WHITE']; MUTED=palette['MUTED']; RED=palette['RED']
    BAR_BG=palette['BAR_BG']; HEADER_BG=palette['HEADER_BG']; CHIP_BG=palette['CHIP_BG']
    IMAGE_BG=palette['IMAGE_BG']; STATUS_BG=palette['STATUS_BG']; NAV_SELECTED=palette['NAV_SELECTED']

def main(page:ft.Page):
    logger=logging.getLogger('pigskin')
    session_alive={'value':True}
    background_tasks=[]
    def disconnected(e):
        session_alive['value']=False
        for task in background_tasks:
            if not task.done():
                task.cancel()
        shutdown_ai_worker()
    page.on_disconnect=disconnected
    page.on_close=disconnected
    page.title='PigSkin AI Studio — Desktop Research'; page.padding=0;page.spacing=0
    page.bgcolor=BG; page.theme_mode=ft.ThemeMode.DARK
    page.window.width=1366;page.window.height=768;page.window.min_width=1000;page.window.min_height=690
    page.theme=ft.Theme(color_scheme_seed=BLUE)
    current_user={'value':None}
    selected={'path':None,'info':None,'result':None,'record_id':None}
    selected_support={'thread_id':None,'status':None,'updated_at':None}
    dataset_ui={'path':None,'path_field':None,'results':None,'report':None}
    experiment_ui={'report':None,'reports':[]}
    result_badge={'control':None}
    support_badge={'control':None}
    page_title=label('Tổng quan',25,WHITE,True)
    subtitle=label('TRUNG TÂM NGHIÊN CỨU • PHÁT HIỆN BỆNH DA HEO',10,CYAN,True)
    workspace_body=ft.Container(padding=20,expand=True)
    nav=[]
    nav_page_indexes=[]
    active_page={'index':0}
    theme_choice={'value':'dark'}
    sidebar_collapsed={'value':False}

    def notify(message,color=CYAN):
        page.snack_bar=ft.SnackBar(content=label(message,13,WHITE),bgcolor=PANEL)
        page.snack_bar.open=True;page.update()

    def admin_dashboard():
        metrics=admin_metrics(current_user['value']['id'])

        def monthly_chart(title,items,color):
            if not items:
                content=ft.Container(height=235,alignment=ft.alignment.center,
                    content=label('Chưa có dữ liệu theo tháng.',12))
            else:
                maximum=max(item['count'] for item in items)
                step=max(1,(maximum+3)//4)
                top=step*4
                sidebar_width=78 if sidebar_collapsed['value'] else 244
                available_width=max(640,page.window.width-sidebar_width-80)
                chart_width=max(300,min(760,(available_width-10)//2))
                chart=ft.BarChart(bar_groups=[
                    ft.BarChartGroup(x=index,bar_rods=[ft.BarChartRod(
                        from_y=0,to_y=item['count'],width=25,color=color,
                        border_radius=4,tooltip=f"{item['month']}: {item['count']}")])
                    for index,item in enumerate(items)],
                    min_y=0,max_y=top,width=chart_width,
                    height=235,groups_space=18,
                    left_axis=ft.ChartAxis(labels=[
                        ft.ChartAxisLabel(value=value,label=label(str(value),9,MUTED))
                        for value in range(0,top+1,step)],labels_size=34),
                    bottom_axis=ft.ChartAxis(labels=[
                        ft.ChartAxisLabel(value=index,label=label(item['month'][5:],9,MUTED))
                        for index,item in enumerate(items)],labels_size=32),
                    horizontal_grid_lines=ft.ChartGridLines(interval=step,color=BORDER,width=1),
                    tooltip_bgcolor=SIDEBAR,interactive=True)
                content=chart
            return block([caption_head(title,'Sáu tháng gần đây',ft.Icons.BAR_CHART),
                content],expand=1,padding=14)

        rate=metrics['disease_percent']
        disease_text=f'{rate:.1f}%' if metrics['classified'] else 'Chưa có dữ liệu'
        disease_note=(f"{metrics['disease_cases']}/{metrics['classified']} kết quả đã phân loại khỏe/bệnh"
            if metrics['classified'] else 'Chỉ tính kết quả chuyên gia đã duyệt; loại trừ chưa kết luận')
        summary=ft.Row([
            kpi('Tài khoản hoạt động',str(metrics['active_accounts']),ft.Icons.PEOPLE,
                CYAN,f"Tổng {metrics['total_accounts']} tài khoản"),
            kpi('Đăng nhập 30 ngày',str(metrics['logins_30d']),ft.Icons.LOGIN,BLUE,
                'Số lần đăng nhập thành công'),
            kpi('Tổng hồ sơ',str(metrics['total_cases']),ft.Icons.FOLDER,TEAL,
                'Hồ sơ đã tiếp nhận'),
            kpi('Chờ duyệt kép',str(metrics['awaiting_second_review']),ft.Icons.RATE_REVIEW,
                AMBER,'Đang chờ chuyên gia thứ hai'),
            kpi('Hồ sơ có kết quả',str(metrics['published']),ft.Icons.CHECK_CIRCLE,
                TEAL,'Đã được chuyên gia thứ hai duyệt')],spacing=9)
        disease=block([caption_head('Tỷ lệ hồ sơ được xác nhận có bệnh',
            'Không phải tỷ lệ mắc bệnh của toàn bộ đàn heo',ft.Icons.HEALTH_AND_SAFETY),
            label(disease_text,34,AMBER,True),label(disease_note,11),
            label('Mẫu số chỉ gồm kết quả đã duyệt có phân loại “khỏe” hoặc “có bệnh”; ca chưa kết luận bị loại.',10)],
            padding=15)
        return [
            ft.Row([ft.Column([label('ADMIN • VẬN HÀNH HỆ THỐNG',10,CYAN,True),
                label('Dashboard quản trị',24,WHITE,True),
                label('Số liệu tổng hợp tài khoản, lượt đăng nhập và luồng hồ sơ.',11)],
                spacing=4),ft.Container(expand=True),
                ft.TextButton('QUẢN LÝ TÀI KHOẢN',icon=ft.Icons.MANAGE_ACCOUNTS,
                    on_click=lambda _:navigate(6)),
                ft.TextButton('HỖ TRỢ',icon=ft.Icons.SUPPORT_AGENT,on_click=lambda _:navigate(7))]),
            summary,
            ft.Row([monthly_chart('Hồ sơ tiếp nhận',metrics['cases_by_month'],CYAN),
                    monthly_chart('Lượt đăng nhập thành công',metrics['logins_by_month'],BLUE)],
                spacing=10,vertical_alignment=ft.CrossAxisAlignment.START),
            disease,
            ft.Container(bgcolor=STATUS_BG,padding=10,border_radius=8,content=label(
                'Số lượt đăng nhập là số lần đăng nhập thành công vào app desktop, không phải số lượt truy cập web. '
                'Dữ liệu LocalDB chỉ tổng hợp trên máy này.',11,AMBER))
        ]

    def expert_dashboard():
        rows=recent(actor_id=current_user['value']['id'])
        summary=case_summary(current_user['value']['id'])
        awaiting=summary['pending']
        second_review=summary['second_review']
        published=summary['published']
        authored=summary['authored']
        queue=[item for item in rows if item.get('result_status') in
            ('not_started','returned','pending_approval')][:10]
        status_names={'not_started':'Chờ chuyên gia','returned':'Cần chỉnh sửa',
                      'pending_approval':'Chờ chuyên gia thứ hai'}
        case_rows=[]
        for item in queue:
            case_rows.append(ft.Container(padding=10,
                border=ft.border.only(bottom=ft.BorderSide(1,BORDER)),
                content=ft.Row([
                    ft.Column([label(f"{item.get('case_id') or 'Hồ sơ cũ'} • {item.get('filename')}",12,CYAN,True),
                        label(item.get('symptoms') or 'Chưa có mô tả triệu chứng',10)],expand=True,spacing=3),
                    label(status_names.get(item.get('result_status'),'Chờ xử lý'),10,AMBER,True)
                ])))
        return [
            ft.Row([ft.Column([label('EXPERT WORKSPACE',10,CYAN,True),
                label('Hàng đợi chuyên gia',24,WHITE,True),
                label('Soạn nhận định hoặc duyệt chéo kết quả của chuyên gia khác.',11)],spacing=4),
                ft.Container(expand=True),
                ft.TextButton('MỞ HỒ SƠ',icon=ft.Icons.VIEW_LIST,on_click=lambda _:navigate(2))]),
            ft.Row([
                kpi('Chờ nhận định',str(awaiting),ft.Icons.RATE_REVIEW,AMBER,
                    'Ca mới hoặc bị trả lại'),
                kpi('Chờ duyệt chéo',str(second_review),ft.Icons.HISTORY,BLUE,
                    'Không thể tự duyệt kết quả mình soạn'),
                kpi('Đã phát hành',str(published),ft.Icons.CHECK_CIRCLE,TEAL,
                    'Đã được chuyên gia thứ hai duyệt'),
                kpi('Đã soạn',str(authored),ft.Icons.EDIT_NOTE,CYAN,
                    'Trên toàn bộ hồ sơ')
            ],spacing=10),
            block([caption_head('Hồ sơ cần chú ý','Tối đa 10 hồ sơ gần đây',ft.Icons.HISTORY),
                *(case_rows or [label('Không có hồ sơ đang chờ xử lý.',13)])],padding=14)
        ]

    def dashboard():
        user=current_user['value']
        if user['role']=='admin':
            return admin_dashboard()
        if user['role']=='expert':
            return expert_dashboard()
        owner_id=user['id'] if user['role']=='user' else None
        rows=recent(owner_id=owner_id,actor_id=user['id'])
        summary=case_summary(user['id'])
        pending=summary['pending']
        inferred=summary['inferred']
        published=summary['published']
        unseen=unseen_result_count(user['id'])
        header=ft.Container(bgcolor=HEADER_BG,border=ft.border.all(1,BORDER),border_radius=8,padding=13,
            content=ft.Row([ft.Column([label(
                'KHU VỰC CỦA BẠN' if user['role']=='user' else 'PIGSKIN RESEARCH / OPERATIONS',
                10,CYAN,True),
                label('Theo dõi hồ sơ của bạn' if user['role']=='user' else 'Điều phối ca nghiên cứu',
                      21,WHITE,True),
                label('Gửi ảnh và theo dõi tiến độ chuyên gia rà soát.'
                      if user['role']=='user' else
                      'Tổng hợp hoạt động tiếp nhận, rà soát và kết quả thực nghiệm.',11)],
                spacing=4,expand=True),
                ft.Container(bgcolor=CHIP_BG,padding=9,border_radius=6,
                    content=label('CHECKPOINT ĐÃ PHÁT HIỆN' if model_ready() else 'ĐANG CHỜ CHECKPOINT',10,AMBER,True)),
                ft.ElevatedButton('GỬI ẢNH' if user['role']=='user' else 'TIẾP NHẬN CA',
                    icon=ft.Icons.ADD,on_click=lambda _:navigate(1),bgcolor=CYAN,color=BG)]))
        stats=ft.Row([kpi('Hồ sơ của bạn' if user['role']=='user' else 'Hồ sơ gần đây',
            str(summary['total']),ft.Icons.FOLDER_OUTLINED,CYAN,'Tổng số hồ sơ của bạn'),
            kpi('Chờ rà soát',str(pending),ft.Icons.HISTORY,AMBER,'Cần chuyên gia xác minh'),
            kpi('Đã có kết quả',str(published),ft.Icons.CHECK_CIRCLE,TEAL,'Đã duyệt chéo'),
            kpi('Thông báo mới',str(unseen),ft.Icons.NOTIFICATIONS,BLUE,'Kết quả chưa xem'),
            kpi('Có kết quả AI',str(inferred),ft.Icons.AUTO_AWESOME,TEAL,'Số hồ sơ chạy được checkpoint')],spacing=10)
        queue_lines=[]
        result_labels={'not_started':'CHỜ CHUYÊN GIA','returned':'CẦN CHỈNH SỬA',
                       'pending_approval':'CHỜ DUYỆT CHÉO','published':'ĐÃ CÓ KẾT QUẢ'}
        for item in rows[:6]:
            status=item.get('result_status') or 'not_started'
            prediction=item['predicted_class'] or 'Chưa có dự đoán AI'
            confidence=f" • {item['confidence']*100:.1f}% softmax" if item['confidence'] is not None else ''
            context=' • '.join(value for value in (item.get('farm_name'),item.get('body_site')) if value)
            queue_lines.append(ft.Container(padding=9,border=ft.border.only(bottom=ft.BorderSide(1,BORDER)),
                content=ft.Row([ft.Column([label(f"{item.get('case_id') or 'Hồ sơ cũ'}  /  {item.get('animal_id') or 'Chưa gắn mã cá thể'}",12,CYAN,True),
                    label(f"{item['filename']} • {context or 'Chưa có thông tin vị trí/cơ sở'}",10),
                    label(f"{prediction}{confidence}",11,WHITE)],spacing=3,expand=True),
                    label(result_labels.get(status,'CHỜ CHUYÊN GIA'),9,
                        TEAL if status=='published' else AMBER,True)])))
        cases=block([ft.Row([caption_head('Hồ sơ của bạn','Theo dõi tiến độ chuyên gia rà soát',ft.Icons.VIEW_LIST),
                    ft.Container(expand=True),ft.TextButton('MỞ LỊCH SỬ',on_click=lambda _:navigate(2))]),
                    *(queue_lines or [label('Chưa có hồ sơ. Tạo ca đầu tiên từ màn hình Phân tích ảnh.',12)]),
                    ft.TextButton('TIẾP NHẬN ẢNH MỚI',icon=ft.Icons.ADD_A_PHOTO,on_click=lambda _:navigate(1))],expand=3,padding=14)
        return [header,stats,cases]

    # Single picker registered once; reusable across visits.
    image=ft.Image(width=480,height=340,fit=ft.ImageFit.CONTAIN,visible=False)
    image_viewer=ft.InteractiveViewer(content=image,width=480,height=340,
        min_scale=1,max_scale=5,pan_enabled=True,scale_enabled=True)
    noimage=ft.Column([ft.Icon(ft.Icons.ADD_PHOTO_ALTERNATE_OUTLINED,size=57,color=CYAN),
        label('CHỌN ẢNH DA HEO',18,WHITE,True),label('JPG / PNG / WEBP • Tối đa 10 MB',12)],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,alignment=ft.MainAxisAlignment.CENTER)
    preview_frame=ft.Container(content=noimage,bgcolor=INNER,height=366,alignment=ft.alignment.center,
                               border=ft.border.all(1,BORDER),border_radius=12)
    file_line=label('Chưa chọn ảnh',12)
    notice=label('AI chưa sẵn sàng. Bạn có thể kiểm tra ảnh và lưu lịch sử.',12,AMBER)
    result_holder=ft.Column(spacing=13,scroll=ft.ScrollMode.AUTO)
    case_identifier=label('CHƯA TẠO HỒ SƠ',13,WHITE,True)
    case_state=label('CHỜ TIẾP NHẬN',11,AMBER,True)
    received_at_label=label('Chưa ghi nhận',11,WHITE,True)
    entered_at={'value':''}
    entered_at_label=label('Thời điểm nhập sẽ hiện tại đây',10,TEAL)
    def stamp_entry_time(e):
        entered_at['value']=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        entered_at_label.value=entered_at['value']
    animal_id_field=ft.TextField(label='Mã cá thể / nhóm',hint_text='Ví dụ: PIG-017',dense=True,expand=True,
                                 on_change=stamp_entry_time)
    farm_field=ft.TextField(label='Trang trại / cơ sở',dense=True,expand=True,on_change=stamp_entry_time)
    body_site_field=ft.TextField(label='Vị trí tổn thương',hint_text='Ví dụ: vùng lưng trái',dense=True,expand=True,
                                 on_change=stamp_entry_time)
    onset_field=ft.TextField(label='Ngày khởi phát (nếu biết)',hint_text='YYYY-MM-DD',
        helper_text='Ngày bệnh bắt đầu theo ghi nhận; không tự lấy ngày nhập hồ sơ.',dense=True,expand=True,
        on_change=stamp_entry_time)
    symptoms_field=ft.TextField(label='Dấu hiệu quan sát',hint_text='Mô tả tổn thương và triệu chứng; chưa phải kết luận bệnh.',
                                multiline=True,min_lines=2,max_lines=3,on_change=stamp_entry_time)

    def render_result():
        r=selected['result']
        result_holder.controls.clear()
        if not r:
            result_holder.controls.extend([ft.Icon(ft.Icons.RADAR,size=70,color=CYAN),
                label('CHỜ PHÂN TÍCH',19,WHITE,True),label('Chọn ảnh và nhấn Bắt đầu kiểm tra.')])
        elif r['mode']!='ai':
            result_holder.controls.extend([ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE,size=60,color=TEAL),
                label('Ảnh hợp lệ — chưa có AI',20,WHITE,True),label(r['message'],13,AMBER)])
        else:
            result_holder.controls.extend([ft.Icon(ft.Icons.AUTO_AWESOME,size=55,color=TEAL),
              label('GỢI Ý MÔ HÌNH • CHỜ CHUYÊN GIA RÀ SOÁT',11,TEAL,True),label(r['label'],21,WHITE,True),
              label(f"Điểm softmax (chưa hiệu chuẩn): {r['confidence']*100:.1f}%",12,AMBER),
              label(f"Thời gian suy luận: {r['elapsed_ms']:.0f} ms",11,WHITE)
                if 'elapsed_ms' in r else label('Chưa đo thời gian suy luận',11),
              label('Các lớp đứng đầu, không phải xác suất chẩn đoán:',11),
              *[meter(s['label'],s['confidence'],CYAN) for s in r['scores']]])
        if selected['record_id']:
            result_holder.controls.append(label(f"Mã hồ sơ: PS-{selected['record_id']:06d} • Cần chuyên gia xác minh",11,AMBER))
        if r and r.get('model_info'):
            result_holder.controls.append(label(f"Model: {r['model_info']}",10))

    def selected_file(e):
        if not e.files: return
        path=e.files[0].path
        try:
            info=inspect_image(path)
            if selected['record_id']:
                reset_case_context()
            selected.update(path=path,info=info,result=None,record_id=None)
            image.src_base64=base64.b64encode(Path(path).read_bytes()).decode('ascii')
            image.visible=True;preview_frame.content=image_viewer
            case_identifier.value='HỒ SƠ SẼ ĐƯỢC TẠO KHI KIỂM TRA'
            case_state.value='ẢNH ĐÃ NẠP • CHỜ PHÂN TÍCH'
            file_line.value=f"{info['name']} • {info['width']}×{info['height']} px • {info['bytes']/1048576:.2f} MB"
            notice.value='Ảnh hợp lệ, có thể bắt đầu kiểm tra.';notice.color=TEAL
            render_result();page.update()
        except (ValueError,OSError) as exc:
            notify(str(exc),RED)
    picker=ft.FilePicker(on_result=selected_file)
    page.overlay.append(picker)

    def selected_dataset_folder(e):
        if not e.path:
            return
        dataset_ui['path']=e.path
        dataset_ui['report']=None
        if dataset_ui['path_field'] is not None:
            dataset_ui['path_field'].value=e.path
        if dataset_ui['results'] is not None:
            dataset_ui['results'].controls.clear()
            dataset_ui['results'].controls.append(label(
                'Đã chọn thư mục. Nhấn “Kiểm tra dataset” để quét ảnh.',11,TEAL))
        page.update()

    dataset_picker=ft.FilePicker(on_result=selected_dataset_folder)
    page.overlay.append(dataset_picker)

    def selected_experiment_file(e):
        if not e.files or not e.files[0].path:
            return
        try:
            experiment_ui['report']=load_experiment_metrics(e.files[0].path)
            experiment_ui['reports']=[item for item in experiment_ui['reports']
                if item['path']!=experiment_ui['report']['path']]
            experiment_ui['reports'].insert(0,experiment_ui['report'])
        except (OSError,ValueError) as exc:
            notify(f'Không thể nạp báo cáo thực nghiệm: {exc}',RED)
            return
        if active_page['index']==4:
            navigate(4)
        notify('Đã nạp số liệu từ file báo cáo thực nghiệm.',TEAL)

    experiment_picker=ft.FilePicker(on_result=selected_experiment_file)
    page.overlay.append(experiment_picker)

    def choose_image(e):
        picker.pick_files(allow_multiple=False,file_type=ft.FilePickerFileType.CUSTOM,
                          allowed_extensions=['jpg','jpeg','png','webp'])

    def reset_case_context():
        entered_at['value']=''
        entered_at_label.value='Thời điểm nhập sẽ hiện tại đây'
        animal_id_field.value=''
        farm_field.value=''
        body_site_field.value=''
        onset_field.value=''
        symptoms_field.value=''
        case_identifier.value='HỒ SƠ SẼ ĐƯỢC TẠO KHI KIỂM TRA'
        case_state.value='ẢNH ĐÃ NẠP • CHỜ PHÂN TÍCH'
        received_at_label.value='Chưa ghi nhận'

    async def process_image(e):
        if not selected['path']:
            notify('Bạn chưa chọn ảnh.');return
        if selected['record_id']:
            notify('Hồ sơ này đã được lưu. Chọn “Ca mới” để tiếp nhận ảnh khác.');return
        button=e.control
        button.disabled=True
        button.text='ĐANG XỬ LÝ...'
        page.update()
        try:
            path=selected['path']
            actor_id=current_user['value']['id']
            info=await asyncio.to_thread(inspect_image,path)
            started=time.perf_counter()
            result=await asyncio.to_thread(predict,path)
            if (not session_alive['value'] or current_user['value'] is None
                    or current_user['value']['id']!=actor_id or selected['path']!=path):
                return
            if result['mode']=='ai':
                result['elapsed_ms']=(time.perf_counter()-started)*1000
            case={'animal_id':animal_id_field.value or '', 'farm_name':farm_field.value or '',
                'body_site':body_site_field.value or '', 'onset_date':onset_field.value or '',
                'symptoms':symptoms_field.value or '', 'entered_at':entered_at['value']}
            rid=await asyncio.to_thread(save,info,result,case,path,actor_id)
            if not session_alive['value']:
                return
            if current_user['value'] is None or current_user['value']['id']!=actor_id:
                return
            selected.update(info=info,result=result,record_id=rid)
            saved_record=next((item for item in recent(
                owner_id=current_user['value']['id'] if current_user['value']['role']=='user' else None,
                actor_id=current_user['value']['id']
            ) if item['id']==rid),None)
            case_identifier.value=f'PS-{rid:06d}'
            case_state.value='ĐÃ LƯU • CHỜ CHUYÊN GIA RÀ SOÁT'
            received_at_label.value=saved_record['created_at'] if saved_record else 'Đã lưu thời gian tiếp nhận'
            notice.value=f'Đã lưu hồ sơ PS-{rid:06d} vào SQL Server LocalDB.'; notice.color=TEAL
            render_result();page.update()
        except (ValueError,OSError,RuntimeError) as exc:
            logger.warning('Case intake rejected: %s', type(exc).__name__)
            if session_alive['value']:
                notice.value=f'Lỗi: {exc}';notice.color=RED;page.update()
        except Exception:
            logger.exception('Case intake failed')
            if session_alive['value']:
                notice.value='Không thể hoàn tất hồ sơ. Vui lòng thử lại hoặc kiểm tra nhật ký ứng dụng.'
                notice.color=RED;page.update()
        finally:
            if session_alive['value']:
                button.disabled=False
                button.text='PHÂN TÍCH'
                page.update()

    def clear_image(e):
        saved_record_id=selected['record_id']
        selected.update(path=None,info=None,result=None)
        preview_frame.content=noimage;image.visible=False;image.src_base64=None
        file_line.value='Chưa chọn ảnh'
        if saved_record_id:
            notice.value=f'Ảnh đã gỡ khỏi phiên xem; hồ sơ PS-{saved_record_id:06d} vẫn được lưu.'
            notice.color=AMBER
        else:
            case_identifier.value='CHƯA TẠO HỒ SƠ'
            case_state.value='CHỜ TIẾP NHẬN'
            received_at_label.value='Chưa ghi nhận'
            notice.value='Chưa chọn ảnh';notice.color=AMBER
        render_result();page.update()

    def start_new_case(e=None):
        selected.update(path=None,info=None,result=None,record_id=None)
        reset_case_context()
        preview_frame.content=noimage;image.visible=False;image.src_base64=None
        file_line.value='Chưa chọn ảnh'
        notice.value='Ca mới chưa có ảnh.';notice.color=AMBER
        render_result();page.update()

    def analysis():
        render_result()
        try:
            ai_spec=model_spec()
            ai_description=(f"{ai_spec['architecture']} • run {ai_spec['run_id']} • "
                f"{ai_spec['class_count']} lớp • input {ai_spec['preprocessing']['resize'][0]}×"
                f"{ai_spec['preprocessing']['resize'][1]}")
        except (OSError,ValueError,KeyError,json.JSONDecodeError):
            ai_description='Chưa có model metadata hợp lệ'
        ai_status=model_status()
        case_header=ft.Container(bgcolor=HEADER_BG,border=ft.border.all(1,BORDER),border_radius=8,padding=12,
            content=ft.Row([ft.Icon(ft.Icons.FOLDER_SHARED_OUTLINED,color=CYAN,size=22),
                ft.Column([label('CASE WORKSPACE • PIG SKIN',10,CYAN,True),case_identifier],spacing=3,expand=True),
                ft.Container(width=1,height=34,bgcolor=BORDER),
                ft.Column([label('TRẠNG THÁI',9,MUTED,True),case_state],spacing=3),
                ft.Container(width=1,height=34,bgcolor=BORDER),
                ft.Column([label('NGÀY TIẾP NHẬN',9,MUTED,True),received_at_label],spacing=3),
                ft.Container(width=1,height=34,bgcolor=BORDER),
                ft.Column([label('PHƯƠNG THỨC',9,MUTED,True),label('ẢNH LÂM SÀNG • RGB',11,WHITE,True)],spacing=3)],spacing=15))
        image_panel=block([caption_head('Image workstation','Ảnh da heo • JPG / PNG / WEBP',ft.Icons.IMAGE_SEARCH),
            ft.Container(content=preview_frame,bgcolor=IMAGE_BG,padding=8,border_radius=8),file_line,
            label('Ảnh nguồn được sao chép vào kho hồ sơ cục bộ khi lưu.',10),
            ft.Row([ft.ElevatedButton('CHỌN ẢNH',icon=ft.Icons.FOLDER_OPEN,on_click=choose_image,bgcolor=CYAN,color=BG),
                ft.OutlinedButton('XÓA ẢNH',icon=ft.Icons.DELETE,on_click=clear_image),
                ft.ElevatedButton('PHÂN TÍCH',icon=ft.Icons.PLAY_ARROW,on_click=process_image,bgcolor=BLUE,color=WHITE)],wrap=True),
            notice],expand=3)
        result_panel=block([ft.Row([caption_head('AI findings','Kết quả hỗ trợ nghiên cứu',ft.Icons.BIOTECH),
                    ft.Container(expand=True),ft.Container(bgcolor=CHIP_BG,padding=8,border_radius=6,
                        content=label('CLASSIFICATION',9,CYAN,True))]),
                    ft.Container(content=result_holder,bgcolor=INNER,padding=18,border_radius=8,height=430,
                        alignment=ft.alignment.top_left),
                    ft.Divider(color=BORDER,height=1),
                    ft.Row([ft.Icon(ft.Icons.MEMORY,color=BLUE,size=17),
                        label(ai_description,11,WHITE,True)]),
                    label(ai_status['message'],11,TEAL if ai_status['available'] else AMBER),
                    label('Đây là phân loại toàn ảnh; hiện chưa có bounding box/segmentation.',10),
                    label('Softmax chưa hiệu chuẩn, không phải xác suất bệnh. Cần chuyên gia xác minh.',10,AMBER)],expand=2)
        clinical_context=block([ft.Row([caption_head('Clinical context','Thông tin quan sát do người tiếp nhận cung cấp',ft.Icons.ASSIGNMENT_OUTLINED),
                ft.Container(expand=True),label('LƯU CÙNG HỒ SƠ',9,TEAL,True),
                ft.OutlinedButton('CA MỚI',icon=ft.Icons.ADD,on_click=start_new_case)]),
            ft.Row([animal_id_field,farm_field],spacing=10),
            ft.Row([body_site_field,onset_field],spacing=10),
            ft.Row([ft.Column([symptoms_field,entered_at_label],spacing=4,expand=True),
                    ft.Column([label('NGÀY KHỞI PHÁT',9,MUTED,True),
                        label('Nhập tay nếu biết; thời điểm nhập được ghi riêng.',10)],spacing=4)]),
            ],padding=14)
        return [case_header,ft.Row([image_panel,result_panel],spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.START),clinical_context]

    def history_view():
        user=current_user['value']
        owner_id=user['id'] if user['role']=='user' else None
        is_expert=user['role']=='expert'
        term=ft.TextField(hint_text='Tìm mã ca, mã heo, cơ sở hoặc tên ảnh...',
                          prefix_icon=ft.Icons.SEARCH,expand=True,dense=True)
        rows_area=ft.Column(spacing=0)
        count=label('',13,CYAN,True)
        page_number={'value':0}
        page_size=25
        page_label=label('',11,WHITE,True)
        previous_button=ft.OutlinedButton('TRƯỚC',icon=ft.Icons.CHEVRON_LEFT)
        next_button=ft.OutlinedButton('SAU',icon=ft.Icons.CHEVRON_RIGHT)
        result_labels={'not_started':'Chờ chuyên gia','returned':'Cần chỉnh sửa',
                       'pending_approval':'Chờ duyệt chéo','published':'Đã có kết quả'}
        review_filter=ft.Dropdown(width=205,dense=True,value='all',label='Trạng thái kết quả',
            options=[ft.dropdown.Option('all','Tất cả trạng thái'),
                     *[ft.dropdown.Option(key,text) for key,text in result_labels.items()]])
        def load(e=None):
            status=None if review_filter.value=='all' else review_filter.value
            total=count_cases(term.value or '',owner_id=owner_id,actor_id=user['id'],status=status)
            pages=max(1,(total+page_size-1)//page_size)
            page_number['value']=min(page_number['value'],pages-1)
            items=recent(term.value or '',owner_id=owner_id,actor_id=user['id'],
                status=status,limit=page_size,offset=page_number['value']*page_size)
            count.value=f'{total} bản ghi phù hợp'
            page_label.value=f"Trang {page_number['value']+1}/{pages}"
            previous_button.disabled=page_number['value']==0
            next_button.disabled=page_number['value']>=pages-1
            rows_area.controls.clear()
            for it in items:
                scores=json.loads(it.get('scores_json') or '[]')
                prediction=it['predicted_class'] or 'Chưa có gợi ý AI'
                score_text=f" • {it['confidence']*100:.1f}% softmax" if it['confidence'] is not None else ''
                status=it.get('result_status') or 'not_started'
                context=' • '.join(value for value in (it.get('farm_name'),it.get('body_site'),
                    f"Khởi phát: {it['onset_date']}" if it.get('onset_date') else '',
                    f"Nhập/cập nhật: {it['entered_at']}" if it.get('entered_at') else '') if value)
                symptoms=it.get('symptoms') or 'Chưa có mô tả quan sát'
                actions=[
                    ft.IconButton(icon=ft.Icons.INFO_OUTLINE,icon_color=CYAN,
                        tooltip='Xem chi tiết hồ sơ',
                        on_click=lambda e,record=it:show_detail(record)),
                    ft.IconButton(icon=ft.Icons.IMAGE_SEARCH,icon_color=TEAL,tooltip='Xem ảnh gốc',
                        disabled=not bool(it.get('image_path')),
                        on_click=lambda e,record=it:show_image(record))]
                if user['role']=='user' and status in ('not_started','returned'):
                    actions.append(ft.IconButton(icon=ft.Icons.EDIT_OUTLINED,icon_color=BLUE,
                        tooltip='Sửa hồ sơ',on_click=lambda e,record=it:edit_case(record)))
                if user['role']=='user' and status=='not_started' \
                        and not it.get('expert_id') and it.get('review_status')=='needs_review':
                    actions.append(ft.IconButton(icon=ft.Icons.DELETE_OUTLINE,
                        icon_color=RED,tooltip='Xóa hồ sơ chưa được chuyên gia xử lý',
                        on_click=lambda e,record=it:confirm_delete(record)))
                if is_expert and status in ('not_started','returned'):
                    actions.append(ft.OutlinedButton('SOẠN KẾT QUẢ',
                        on_click=lambda e,record=it:compose_result(record)))
                elif is_expert and status=='pending_approval':
                    if it.get('expert_id')==user['id']:
                        actions.append(label('Chờ chuyên gia khác duyệt',10,AMBER,True))
                    else:
                        actions.append(ft.ElevatedButton('DUYỆT CHÉO',
                            on_click=lambda e,record=it:review_result(record),
                            bgcolor=TEAL,color=BG))
                else:
                    actions.append(label(result_labels.get(status,status),10,
                        TEAL if status=='published' else AMBER,True))
                line=ft.Row([ft.Column([
                    label(f"{it['case_id'] or 'Hồ sơ cũ'} • {it['animal_id'] or 'Chưa gắn mã cá thể'}",12,CYAN,True),
                    label(f"{it['filename']} • Tiếp nhận: {it['created_at']}",10),
                    label(f"{context or 'Chưa có thông tin cơ sở/vị trí'}",10),
                    label(f"Mô tả: {symptoms}",10,WHITE),
                    label(f"{prediction}{score_text} • {len(scores)} lớp đã lưu",11,WHITE),
                    *([label(f"Kết quả chuyên gia: {it.get('expert_result')}",11,TEAL),
                       label(f"Ghi chú: {it.get('expert_notes')}",10)
                       ] if status=='published' and it.get('expert_result') else []),
                    *([label(f"Lý do cần chỉnh sửa: {it.get('review_note')}",10,AMBER)
                       ] if status=='returned' and it.get('review_note') else [])],
                    spacing=3,expand=True),*actions],spacing=12)
                rows_area.controls.append(ft.Container(content=line,padding=10,
                   border=ft.border.only(bottom=ft.BorderSide(1,BORDER))))
            if not items:rows_area.controls.append(label('Chưa có lượt kiểm tra nào.',14))
            page.update()

        def confirm_delete(record):
            dialog=ft.AlertDialog(modal=True,
                title=label(f"Xóa hồ sơ {record.get('case_id') or record['id']}?",17,WHITE,True),
                content=ft.Container(width=460,content=ft.Column([
                    label('Chỉ hồ sơ chưa được chuyên gia tiếp nhận mới có thể xóa.',12),
                    label('Thao tác này xóa hồ sơ và ảnh lưu trong kho ứng dụng; không thể hoàn tác.',
                        11,AMBER)],spacing=8,tight=True)),
                actions=[ft.TextButton('HỦY',on_click=lambda _:page.close(dialog)),
                    ft.ElevatedButton('XÓA HỒ SƠ',icon=ft.Icons.DELETE,
                        on_click=lambda _:delete_record(record,dialog),
                        bgcolor=RED,color=WHITE)],bgcolor=PANEL)
            page.open(dialog)

        def delete_record(record,dialog):
            try:
                delete(record['id'],user['id'])
            except ValueError as exc:
                page.close(dialog)
                notify(str(exc),RED)
                load()
                return
            except OSError as exc:
                page.close(dialog)
                notify(f'Hồ sơ đã xóa nhưng không thể xóa tệp ảnh lưu trữ: {exc}',RED)
                load()
                return
            page.close(dialog)
            load()
            notify('Đã xóa hồ sơ và ảnh lưu trữ.')

        def compose_result(record):
            category_names={'healthy':'Khỏe / không thấy dấu hiệu bệnh',
                            'condition':'Có dấu hiệu bệnh',
                            'inconclusive':'Chưa đủ thông tin kết luận'}
            category=ft.Dropdown(label='Phân loại kết luận',value=record.get('result_category')
                if record.get('result_category') in category_names else 'inconclusive',
                options=[ft.dropdown.Option(key,value) for key,value in category_names.items()])
            result_field=ft.TextField(label='Kết quả chuyên gia',multiline=True,min_lines=3,
                max_lines=6,value=record.get('expert_result') or '')
            notes_field=ft.TextField(label='Lưu ý / hướng dẫn tiếp theo',multiline=True,
                min_lines=2,max_lines=4,value=record.get('expert_notes') or '')
            def submit_result(e):
                try:
                    submit_expert_result(record['id'],user['id'],category.value or '',
                        result_field.value or '',notes_field.value or '')
                    page.close(dialog)
                    load()
                    notify('Đã gửi kết quả vào hàng chờ duyệt chéo.')
                except ValueError as exc:
                    notify(str(exc),RED)
            dialog=ft.AlertDialog(modal=True,
                title=label(f"Soạn kết quả • {record.get('case_id')}",17,WHITE,True),
                content=ft.Container(width=560,content=ft.Column([
                    label('Kết quả sẽ chưa hiển thị cho người dùng cho đến khi chuyên gia thứ hai duyệt.',11,AMBER),
                    category,result_field,notes_field],spacing=10,tight=True,
                    scroll=ft.ScrollMode.AUTO)),
                actions=[ft.TextButton('HỦY',on_click=lambda e:page.close(dialog)),
                    ft.ElevatedButton('GỬI DUYỆT CHÉO',on_click=submit_result,
                        bgcolor=CYAN,color=BG)],bgcolor=PANEL)
            page.open(dialog)
        def review_result(record):
            feedback=ft.TextField(label='Ghi chú cho chuyên gia (bắt buộc nếu trả lại)',
                multiline=True,min_lines=2,max_lines=4)
            category_names={'healthy':'Khỏe / không thấy dấu hiệu bệnh',
                            'condition':'Có dấu hiệu bệnh',
                            'inconclusive':'Chưa đủ thông tin kết luận'}
            content=ft.Column([
                label(f"Kết luận: {category_names.get(record.get('result_category'), 'Chưa phân loại')}",
                    12,CYAN,True),
                label(record.get('expert_result') or '',13,WHITE),
                label(f"Ghi chú: {record.get('expert_notes') or 'Không có'}",11),
                label('Người soạn: '+str(record.get('expert_id')),10,MUTED),
                feedback],spacing=9,tight=True,scroll=ft.ScrollMode.AUTO)
            def decide(approve):
                try:
                    review_expert_result(record['id'],user['id'],approve,feedback.value or '')
                    page.close(dialog)
                    load()
                    notify('Kết quả đã được phát hành cho người dùng.' if approve
                        else 'Đã trả kết quả cho chuyên gia chỉnh sửa.')
                except ValueError as exc:
                    notify(str(exc),RED)
            dialog=ft.AlertDialog(modal=True,
                title=label(f"Duyệt chéo • {record.get('case_id')}",17,WHITE,True),
                content=ft.Container(width=560,content=content),
                actions=[ft.TextButton('TRẢ CHỈNH SỬA',
                        on_click=lambda e:decide(False)),
                    ft.ElevatedButton('DUYỆT VÀ PHÁT HÀNH',
                        on_click=lambda e:decide(True),bgcolor=TEAL,color=BG)],
                bgcolor=PANEL)
            page.open(dialog)
        def show_image(record):
            try:
                image_path=authorized_image_path(record['id'],user['id'])
            except ValueError as exc:
                notify(str(exc),RED);return
            encoded=base64.b64encode(image_path.read_bytes()).decode('ascii')
            dialog=ft.AlertDialog(modal=True,title=label(f"Ảnh hồ sơ • {record['filename']}",16,WHITE,True),
                content=ft.Container(width=900,height=600,bgcolor=INNER,alignment=ft.alignment.center,
                    content=ft.InteractiveViewer(content=ft.Image(src_base64=encoded,
                        width=840,height=540,fit=ft.ImageFit.CONTAIN),
                        min_scale=1,max_scale=5,pan_enabled=True,scale_enabled=True)),
                actions=[ft.TextButton('Đóng',on_click=lambda e:page.close(dialog))],bgcolor=PANEL)
            page.open(dialog)
        def show_detail(record):
            status=record.get('result_status') or 'not_started'
            if user['role']=='user' and status=='published':
                try:
                    mark_result_seen(user['id'],record['id'])
                    update_result_badge()
                except ValueError as exc:
                    notify(str(exc),RED)
                    return
            timeline=[f"Tiếp nhận: {record.get('created_at') or '—'}"]
            if record.get('result_submitted_at'):
                timeline.append(f"Chuyên gia gửi duyệt: {record['result_submitted_at']}")
            if record.get('approved_at'):
                timeline.append(f"Phát hành: {record['approved_at']}")
            if status=='returned':
                timeline.append('Trả chỉnh sửa: '+str(record.get('review_note') or ''))
            details=[
                label(record.get('case_id') or f"PS-{record['id']:06d}",19,CYAN,True),
                label('Trạng thái: '+result_labels.get(status,status),12,TEAL if status=='published' else AMBER,True),
                label('Mã cá thể: '+(record.get('animal_id') or '—'),11,WHITE),
                label('Cơ sở: '+(record.get('farm_name') or '—'),11,WHITE),
                label('Vị trí: '+(record.get('body_site') or '—'),11,WHITE),
                label('Ngày khởi phát: '+(record.get('onset_date') or '—'),11,WHITE),
                label('Dấu hiệu: '+(record.get('symptoms') or '—'),11,WHITE),
                ft.Divider(color=BORDER),label('TIẾN TRÌNH',11,CYAN,True),
                *[label(line,11,WHITE) for line in timeline]
            ]
            if status=='published' and record.get('expert_result'):
                details.extend([ft.Divider(color=BORDER),label('KẾT QUẢ ĐÃ DUYỆT',11,TEAL,True),
                    label(record['expert_result'],12,WHITE),
                    label(record.get('expert_notes') or '',11)])
            dialog=ft.AlertDialog(modal=True,title=label('Chi tiết hồ sơ',17,WHITE,True),
                content=ft.Container(width=610,height=510,content=ft.Column(details,
                    scroll=ft.ScrollMode.AUTO,spacing=9)),
                actions=[ft.TextButton('ĐÓNG',on_click=lambda _:page.close(dialog))],bgcolor=PANEL)
            page.open(dialog)
        def edit_case(record):
            animal=ft.TextField(label='Mã cá thể / nhóm',value=record.get('animal_id') or '',dense=True)
            farm=ft.TextField(label='Trang trại / cơ sở',value=record.get('farm_name') or '',dense=True)
            site=ft.TextField(label='Vị trí tổn thương',value=record.get('body_site') or '',dense=True)
            onset=ft.TextField(label='Ngày khởi phát (nếu biết)',value=record.get('onset_date') or '',
                hint_text='YYYY-MM-DD',helper_text='Sửa theo ghi nhận thực tế; không phải thời điểm nhập.',dense=True)
            symptoms=ft.TextField(label='Dấu hiệu quan sát',value=record.get('symptoms') or '',
                multiline=True,min_lines=3,max_lines=5)
            def save_changes(e):
                changed_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                changed=update_case(record['id'],{'animal_id':animal.value or '',
                    'farm_name':farm.value or '', 'body_site':site.value or '',
                    'onset_date':onset.value or '', 'symptoms':symptoms.value or '',
                    'entered_at':changed_at},owner_id=owner_id)
                if not changed:
                    page.close(dialog)
                    notify('Không tìm thấy hồ sơ hoặc bạn không có quyền sửa.',RED)
                    load()
                    return
                page.close(dialog)
                load()
                notify('Đã cập nhật hồ sơ và thời điểm chỉnh sửa.')
            dialog=ft.AlertDialog(modal=True,title=label(f"Sửa hồ sơ {record.get('case_id') or record['id']}",17,WHITE,True),
                content=ft.Container(width=520,content=ft.Column([
                    animal,farm,site,onset,symptoms,
                    label(f"Tiếp nhận lúc: {record['created_at']}",10,MUTED)],spacing=9,tight=True,
                    scroll=ft.ScrollMode.AUTO)),
                actions=[ft.TextButton('Hủy',on_click=lambda e:page.close(dialog)),
                    ft.ElevatedButton('LƯU THAY ĐỔI',icon=ft.Icons.SAVE,on_click=save_changes,
                        bgcolor=CYAN,color=BG)],actions_alignment=ft.MainAxisAlignment.END,bgcolor=PANEL)
            page.open(dialog)
        def reset_page(e=None):
            page_number['value']=0
            load()
        def change_page(direction):
            page_number['value']+=direction
            load()
        previous_button.on_click=lambda _:change_page(-1)
        next_button.on_click=lambda _:change_page(1)
        term.on_change=reset_page
        review_filter.on_change=reset_page
        load()
        return [block([caption_head('Kết quả của tôi' if user['role']=='user' else
                    'Hồ sơ và duyệt chéo','Kết quả chỉ phát hành sau khi được chuyên gia thứ hai duyệt.',
                    ft.Icons.HISTORY),
                ft.Row([term,review_filter,ft.OutlinedButton('Làm mới',icon=ft.Icons.REFRESH,on_click=load)]),
                ft.Row([label('HỒ SƠ / QUAN SÁT / NHẬN ĐỊNH',10,CYAN,True),ft.Container(expand=True),
                    label('SỬA',10,BLUE,True),label('TRẠNG THÁI',10,CYAN,True),label('XÓA',10,RED,True)],spacing=12),count,
                ft.Container(content=rows_area,bgcolor=INNER,border_radius=10,padding=8),
                ft.Row([ft.Container(expand=True),previous_button,page_label,next_button])],padding=20)]

    def support_view():
        user=current_user['value']
        is_user=user['role']=='user'
        is_staff=user['role'] in ('expert','admin')
        threads=support_threads(user['id'],user['role'])
        if selected_support['thread_id'] is not None and not any(
                item['id']==selected_support['thread_id'] for item in threads):
            selected_support['thread_id']=None
        selected_thread=next((item for item in threads
            if item['id']==selected_support['thread_id']),None)
        selected_support['status']=selected_thread['status'] if selected_thread else None
        selected_support['updated_at']=selected_thread['updated_at'] if selected_thread else None
        if selected_thread:
            mark_support_thread_seen(selected_thread['id'],user['id'],user['role'])
            update_support_badge()
        thread_list=ft.Column(spacing=4,scroll=ft.ScrollMode.AUTO,expand=True)
        status_names={'open':'Chờ trả lời','answered':'Đã trả lời','closed':'Đã đóng'}

        def open_thread(thread_id):
            selected_support['thread_id']=thread_id
            navigate(7)

        def create_question(e=None):
            subject=ft.TextField(label='Tiêu đề',max_length=200)
            body=ft.TextField(label='Câu hỏi',multiline=True,min_lines=3,max_lines=6)
            def submit_question(_):
                try:
                    thread_id=create_support_thread(user['id'],subject.value or '',body.value or '')
                    page.close(dialog)
                    selected_support['thread_id']=thread_id
                    navigate(7)
                    notify('Đã gửi yêu cầu hỗ trợ.')
                except ValueError as exc:
                    notify(str(exc),RED)
            dialog=ft.AlertDialog(modal=True,title=label('Tạo yêu cầu hỗ trợ',17,WHITE,True),
                content=ft.Container(width=520,content=ft.Column(
                    [subject,body],spacing=10,tight=True)),
                actions=[ft.TextButton('HỦY',on_click=lambda _:page.close(dialog)),
                    ft.ElevatedButton('GỬI CÂU HỎI',on_click=submit_question,
                        bgcolor=CYAN,color=BG)],bgcolor=PANEL)
            page.open(dialog)

        for thread in threads:
            title=thread.get('subject') or 'Yêu cầu hỗ trợ'
            preview=(thread.get('last_message') or '').replace('\r',' ').replace('\n',' ')
            if len(preview)>90:
                preview=preview[:87]+'...'
            thread_list.controls.append(ft.Container(
                bgcolor=NAV_SELECTED if selected_thread and thread['id']==selected_thread['id'] else INNER,
                border_radius=8,padding=10,ink=True,
                on_click=lambda _,thread_id=thread['id']:open_thread(thread_id),
                content=ft.Column([
                    label(title,12,WHITE,True),
                    label(f"{status_names.get(thread['status'],thread['status'])} • "
                        f"{thread.get('user_name','')}",9,CYAN),
                    label(preview,10)],spacing=4)))
        if not threads:
            thread_list.controls.append(label('Chưa có yêu cầu hỗ trợ nào.',11))

        detail_controls=[]
        if selected_thread:
            messages=support_messages(selected_thread['id'],user['id'],user['role'])
            for message in messages:
                sender=message['sender_name']
                if message['sender_role'] in ('expert','admin'):
                    sender+=f" • {message['sender_role']}"
                detail_controls.append(ft.Container(
                    bgcolor=CHIP_BG if message['sender_id']!=user['id'] else INNER,
                    border_radius=8,padding=10,content=ft.Column([
                        ft.Row([label(sender,10,CYAN,True),ft.Container(expand=True),
                            label(message['created_at'],9,MUTED)]),
                        label(message['body'],12,WHITE)
                    ],spacing=5)))
            user_message_count=int(selected_thread.get('user_message_count') or 0)
            staff_message_count=int(selected_thread.get('staff_message_count') or 0)
            remaining_before_reply=max(0,3-user_message_count)
            waiting_at_limit=(is_user and staff_message_count==0
                and remaining_before_reply==0)
            if is_user and staff_message_count==0 and selected_thread['status']!='closed':
                limit_text=(
                    f'Chuyên gia chưa phản hồi. Bạn chỉ có thể gửi thêm '
                    f'{remaining_before_reply} tin trước khi phải chờ chuyên gia.'
                    if remaining_before_reply else
                    'Bạn đã gửi đủ 3 tin. Hãy chờ chuyên gia trả lời để tiếp tục trao đổi.'
                )
                detail_controls.append(ft.Container(bgcolor=STATUS_BG,border_radius=8,padding=11,
                    content=ft.Row([
                        ft.Icon(ft.Icons.INFO_OUTLINE,color=AMBER,size=18),
                        label(limit_text,10,AMBER,True)
                    ])))
            if selected_thread['status']=='closed':
                detail_controls.extend([ft.Divider(color=BORDER),
                    ft.Container(bgcolor=STATUS_BG,border_radius=8,padding=12,
                        content=ft.Row([
                            ft.Icon(ft.Icons.LOCK_OUTLINE,color=AMBER,size=19),
                            label('CUỘC TRÒ CHUYỆN ĐÃ ĐÓNG',11,AMBER,True),
                            ft.Container(expand=True),
                            label('Hãy tạo yêu cầu hỗ trợ mới nếu cần trao đổi thêm.',10)
                        ]))])
            elif waiting_at_limit:
                pass
            else:
                reply=ft.TextField(label='Nhập câu trả lời',multiline=True,min_lines=2,max_lines=4)
                def send_reply(e=None):
                    try:
                        reply_support_thread(selected_thread['id'],user['id'],user['role'],
                            reply.value or '')
                        navigate(7)
                        notify('Đã gửi trả lời.')
                    except ValueError as exc:
                        notify(str(exc),RED)
                detail_controls.extend([ft.Divider(color=BORDER),reply,
                    ft.Row([ft.Container(expand=True),
                        ft.ElevatedButton('GỬI TRẢ LỜI',icon=ft.Icons.SEND,
                            on_click=send_reply,bgcolor=CYAN,color=BG)])])
            if is_staff and selected_thread['status']!='closed':
                def close_thread(e=None):
                    try:
                        close_support_thread(selected_thread['id'],user['id'])
                        notify('Đã đóng yêu cầu hỗ trợ.')
                        navigate(7)
                    except ValueError as exc:
                        notify(str(exc),RED)
                detail_controls.append(ft.TextButton('ĐÓNG YÊU CẦU',
                    icon=ft.Icons.CHECK,on_click=close_thread))
        else:
            detail_controls.append(label(
                'Chọn một yêu cầu ở danh sách để xem nội dung và trả lời.',12))

        heading=ft.Row([
            ft.Column([label('HỖ TRỢ • HỎI ĐÁP',10,CYAN,True),
                label('Trung tâm hỗ trợ',23,WHITE,True),
                label('Yêu cầu được lưu trong LocalDB; hội thoại tự đóng sau 30 phút không có phản hồi mới từ chuyên gia.',11)],
                spacing=4,expand=True),
            *([ft.ElevatedButton('CÂU HỎI MỚI',icon=ft.Icons.ADD,
                    on_click=create_question,bgcolor=CYAN,color=BG)] if is_user else [])
        ])
        return [heading,ft.Row([
            block([caption_head('Yêu cầu hỗ trợ',
                'Bạn dùng tên và email tài khoản trong hội thoại.',ft.Icons.SUPPORT_AGENT),
                thread_list],expand=1,padding=12),
            block([caption_head(
                selected_thread.get('subject','Nội dung hội thoại') if selected_thread
                else 'Nội dung hội thoại',
                ('Người dùng: '+selected_thread.get('user_name',''))
                if selected_thread and not is_user else None,
                ft.Icons.FORUM),
                ft.Column(detail_controls,spacing=9,scroll=ft.ScrollMode.AUTO,expand=True)],
                expand=2,padding=12)
        ],spacing=12,vertical_alignment=ft.CrossAxisAlignment.START)]

    def dataset():
        path_field=ft.TextField(label='Thư mục dataset',value=dataset_ui['path'] or '',
            read_only=True,expand=True,dense=True)
        results=ft.Column(spacing=12)
        scan_button=ft.ElevatedButton('KIỂM TRA DATASET',icon=ft.Icons.FACT_CHECK,
            bgcolor=CYAN,color=BG)
        dataset_ui['path_field']=path_field
        dataset_ui['results']=results

        def render_report(report):
            results.controls.clear()
            results.controls.append(ft.Column([
                ft.Row([
                    kpi('Ảnh hợp lệ',str(report['valid_images']),ft.Icons.IMAGE,TEAL,
                        f"{report['image_files']} file ảnh được tìm thấy"),
                    kpi('Ảnh lỗi',str(report['corrupt_images']),ft.Icons.BROKEN_IMAGE,RED,
                        'Không đọc/kiểm tra được')
                ],spacing=9),
                ft.Row([
                    kpi('Ảnh trùng',str(report['duplicate_extras']),ft.Icons.CONTENT_COPY,AMBER,
                        f"{report['duplicate_groups']} nhóm trùng byte"),
                    kpi('Trùng khác split',str(report['cross_split_duplicate_groups']),
                        ft.Icons.WARNING_AMBER,AMBER,'Có thể gây rò rỉ giữa các tập')
                ],spacing=9)
            ],spacing=9))
            split_rows=[
                ft.Row([label(split,11,WHITE,True),ft.Container(expand=True),
                        label(str(count),11,CYAN,True)])
                for split,count in report['split_counts'].items()
            ]
            class_rows=[]
            largest=max(report['class_counts'].values(),default=1)
            for class_name,count in report['class_counts'].items():
                class_rows.append(meter(class_name,count/largest,CYAN,f'{count} ảnh'))
            results.controls.append(ft.Row([
                block([caption_head('Phân bố theo split',
                    f"Cấu trúc phát hiện: {report['layout']}",ft.Icons.DONUT_LARGE),
                    *(split_rows or [label('Chưa xác định được train/validation/test.',11,AMBER)])],
                    expand=1,padding=14),
                block([caption_head('Số ảnh theo lớp','Chỉ tính ảnh đọc được',ft.Icons.CATEGORY),
                    *(class_rows or [label('Chưa tìm thấy ảnh hợp lệ theo lớp.',11,AMBER)])],
                    expand=2,padding=14)
            ],spacing=10,vertical_alignment=ft.CrossAxisAlignment.START))
            warning_rows=[ft.Row([ft.Icon(ft.Icons.WARNING_AMBER,color=AMBER,size=17),
                label(message,11,AMBER)]) for message in report['warnings']]
            if not warning_rows:
                warning_rows.append(ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE,color=TEAL,size=17),
                    label('Không phát hiện vấn đề cấu trúc phổ biến.',11,TEAL)]))
            details=[
                label('Kiểm tra này không xác nhận nhãn có đúng về chuyên môn hay không.',10,MUTED),
                label('Ảnh trùng được xác định bằng SHA-256 giống hệt; ảnh gần giống chưa được phát hiện.',10,MUTED),
            ]
            if report['corrupt_examples']:
                details.append(label('Ví dụ ảnh lỗi: '+', '.join(report['corrupt_examples'][:8]),10,RED))
            if report['empty_classes']:
                details.append(label('Thư mục lớp rỗng: '+', '.join(report['empty_classes'][:8]),10,AMBER))
            results.controls.append(block([
                caption_head('Cảnh báo kiểm tra','Chỉ đọc file, không sửa/xóa dữ liệu',ft.Icons.RULE),
                *warning_rows,*details],padding=14))

        if dataset_ui['report'] is not None:
            render_report(dataset_ui['report'])
        else:
            results.controls.append(label(
                'Chọn thư mục có dạng lớp/ảnh hoặc train, validation, test/lớp/ảnh để bắt đầu.',
                11))

        def choose_dataset_folder(e):
            dataset_picker.get_directory_path(dialog_title='Chọn thư mục dataset',
                initial_directory=dataset_ui['path'])

        async def run_dataset_audit(e):
            folder=dataset_ui['path']
            if not folder:
                notify('Hãy chọn thư mục dataset trước.',AMBER)
                return
            scan_button.disabled=True
            scan_button.text='ĐANG KIỂM TRA...'
            page.update()
            try:
                report=await asyncio.to_thread(audit_dataset,folder)
            except (OSError,ValueError) as exc:
                logger.warning('Dataset audit failed: %s', type(exc).__name__)
                if session_alive['value']:
                    scan_button.disabled=False
                    scan_button.text='KIỂM TRA DATASET'
                    notify(f'Không thể kiểm tra dataset: {exc}',RED)
                return
            dataset_ui['report']=report
            if not session_alive['value']:
                return
            scan_button.disabled=False
            scan_button.text='KIỂM TRA LẠI'
            navigate(3)

        scan_button.on_click=run_dataset_audit
        report=dataset_ui['report']
        report_stats=ft.Column([
            ft.Row([
                kpi('Tổng ảnh',str(report['image_files']) if report else '—',ft.Icons.IMAGE,BLUE,'Từ lần quét hiện tại'),
                kpi('Training',str(report['split_counts'].get('train',0)) if report else '—',ft.Icons.SCHOOL,BLUE,'Từ lần quét hiện tại')
            ],spacing=10),
            ft.Row([
                kpi('Validation',str(report['split_counts'].get('validation',0)) if report else '—',ft.Icons.VERIFIED,AMBER,'Từ lần quét hiện tại'),
                kpi('Testing',str(report['split_counts'].get('test',0)) if report else '—',ft.Icons.FACT_CHECK,TEAL,'Từ lần quét hiện tại')
            ],spacing=10)
        ],spacing=10)
        return [
            ft.Row([ft.Column([label('DATASET INTELLIGENCE',10,CYAN,True),
                label('Kiểm tra dữ liệu ảnh',23,WHITE,True),
                label('Quét cấu trúc lớp/split, ảnh hỏng, trùng lặp và mất cân bằng.',11)],
                spacing=4),ft.Container(expand=True),
                label('KIỂM TRA CỤC BỘ • CHỈ ĐỌC',10,TEAL,True)]),
            block([caption_head('Chọn nguồn dữ liệu',
                    'Hỗ trợ class/image hoặc train, validation, test/class/image.',
                    ft.Icons.FOLDER_OPEN),
                ft.Row([path_field,ft.OutlinedButton('CHỌN THƯ MỤC',
                    icon=ft.Icons.FOLDER_OPEN,on_click=choose_dataset_folder),scan_button],
                    spacing=8,wrap=True),
                results],padding=14),
            block([caption_head('Thống kê từ thư mục đã chọn',
                    'Chỉ hiển thị số liệu từ lần kiểm tra dataset trong phiên này.',
                    ft.Icons.DESCRIPTION),report_stats,
                label('Dataset version: '+(report.get('dataset_version') or 'Chưa có dataset_manifest.json hợp lệ')
                    if report else 'Dataset version: chưa xác định',10,TEAL if report and report.get('dataset_version') else AMBER),
                label('Chưa chọn hoặc chưa quét dataset.' if not report else
                    f"Nguồn: {report['root']}",10,AMBER)],padding=14)
        ]

    def training():
        report=experiment_ui['report']
        report_data=report or {}
        report_metrics=report_data.get('metrics',{})
        metric_colors={
            'validation_macro_f1':TEAL,
            'test_macro_f1':BLUE,
            'test_accuracy':AMBER,
            'validation_accuracy':CYAN,
            'test_macro_precision':TEAL,
            'test_macro_recall':BLUE,
        }

        def metric_value(name):
            value=report_metrics.get(name)
            if value is None:
                return '—'
            return f'{value*100:.2f}%' if name=='test_accuracy' else f'{value:.4f}'

        def choose_report(e):
            experiment_picker.pick_files(dialog_title='Chọn báo cáo thực nghiệm JSON',
                allow_multiple=False,file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=['json'])

        summary_cards=[
            kpi('Best epoch',
                str(report_data['best_epoch']) if report_data.get('best_epoch') else '—',
                ft.Icons.TIMELINE,BLUE,
                report_data.get('run_id') or
                ('Chưa có thông tin run' if report else 'Chưa nạp báo cáo')),
            *[kpi(METRIC_NAMES[name],metric_value(name),
                ft.Icons.ANALYTICS if 'f1' in name else ft.Icons.TRACK_CHANGES,
                metric_colors[name],'Đọc từ file báo cáo' if name in report_metrics
                else 'Không có trong báo cáo')
              for name in METRIC_NAMES]
        ]
        metrics=ft.Column([ft.Row(summary_cards[index:index+3],spacing=10)
            for index in range(0,len(summary_cards),3)],spacing=10)

        performance_items=[]
        for name,title in METRIC_NAMES.items():
            if name in report_metrics:
                performance_items.append(meter(title,report_metrics[name],
                    metric_colors[name],metric_value(name)))
        if not performance_items:
            performance_items.append(label(
                'Chưa có chỉ số. Hãy nạp báo cáo JSON do script đánh giá xuất ra.',11,AMBER))
        performance=block([
            caption_head('Chỉ số đánh giá','Số liệu được đọc trực tiếp từ báo cáo đã chọn.',
                ft.Icons.ANALYTICS),
            *performance_items,
            label('Chỉ số không có trong file sẽ để trống; ứng dụng không tự suy diễn.',10,AMBER)
        ],expand=1,padding=14)

        experiment_details=[
            ft.Row([label('Run ID',11),ft.Container(expand=True),
                label(report_data.get('run_id') or '—',11,WHITE,True)]),
            ft.Row([label('Kiến trúc',11),ft.Container(expand=True),
                label(report_data.get('architecture') or '—',11,WHITE,True)]),
            ft.Row([label('Best epoch',11),ft.Container(expand=True),
                label(str(report_data['best_epoch']) if report_data.get('best_epoch') else '—',
                    11,WHITE,True)]),
            ft.Row([label('Nguồn',11),ft.Container(expand=True),
                label(report_data.get('source') or 'Chưa nạp báo cáo',10,
                    TEAL if report else AMBER,True)]),
            *([label(f"File: {report_data['path']}",9,MUTED,selectable=True)] if report else []),
            ft.Divider(color=BORDER),
            label('Ứng dụng chỉ đọc báo cáo; không huấn luyện hoặc chạy đánh giá model tại đây.',10,AMBER)
        ]
        reproducibility=block([
            ft.Row([caption_head('Thông tin run','Metadata lấy từ báo cáo thực nghiệm',
                ft.Icons.SCIENCE_OUTLINED),ft.Container(expand=True),
                ft.OutlinedButton('NẠP FILE JSON',icon=ft.Icons.UPLOAD_FILE,
                    on_click=choose_report)]),
            *experiment_details
        ],expand=1,padding=14)

        class_results=[]
        if report and report['per_class']:
            for entry in report['per_class']:
                values=' • '.join(
                    f'{name.upper()} {entry[name]:.3f}'
                    for name in ('precision','recall','f1') if name in entry
                )
                class_results.append(ft.Row([
                    label(entry['class_name'],11,WHITE,True),
                    ft.Container(expand=True),label(values or 'Không có chỉ số',10)
                ],spacing=10))
        per_class=block([
            caption_head('Đánh giá theo lớp','Chỉ hiển thị trường có trong file JSON.',
                ft.Icons.CATEGORY),
            *(class_results or [label(
                'Báo cáo chưa có precision/recall/F1 theo từng lớp.',11,AMBER)])
        ],padding=14)
        loss_rows=[ft.Row([label(name.replace('_',' ').title(),11),ft.Container(expand=True),
            label(f'{value:.4f}',11,WHITE,True)])
            for name,value in report_data.get('losses',{}).items()]
        run_rows=[ft.Row([label(item.get('run_id') or Path(item['path']).name,11,WHITE,True),
            ft.Container(expand=True),label(item.get('source') or '',10)])
            for item in experiment_ui['reports']]
        confusion=report_data.get('confusion_matrix')
        matrix_rows=[]
        if confusion:
            for index,row in enumerate(confusion):
                matrix_rows.append(label(
                    f"{report_data['per_class'][index]['class_name']}: " + '  '.join(map(str,row)),10,WHITE,
                    font_family='Consolas'))
        return [
            ft.Row([ft.Column([label('TRAINING METRICS',10,CYAN,True),
                    label('Đánh giá thực nghiệm',23,WHITE,True),
                    label('Nạp JSON từ script đánh giá để hiển thị số liệu của từng run.',11)],
                    spacing=4),ft.Container(expand=True),
                ft.Container(bgcolor=STATUS_BG,padding=9,border_radius=6,
                    content=label('CHƯA NẠP BÁO CÁO' if not report else 'BÁO CÁO ĐÃ NẠP',
                        10,AMBER if not report else TEAL,True))]),
            metrics,ft.Row([performance,reproducibility],spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.START),
            per_class,
            block([caption_head('Loss và lịch sử run','Chỉ các file JSON đã nạp trong phiên hiện tại.',ft.Icons.TIMELINE),
                *(loss_rows or [label('Báo cáo chưa có số liệu loss.',11,AMBER)]),
                ft.Divider(color=BORDER),*(run_rows or [label('Chưa nạp run nào.',11)])],padding=14),
            *([block([caption_head('Confusion matrix',
                'Hàng: nhãn thật • Cột: dự đoán, theo thứ tự per_class.',ft.Icons.GRID_ON),
                *matrix_rows],padding=14)] if matrix_rows else [])
        ]

    def model():
        return build_model_view(PALETTES[theme_choice['value']],label,block,caption_head)

    def accounts_view():
        role_names={'user':'Người dùng','expert':'Chuyên gia','admin':'Quản trị viên'}
        role_options=[ft.dropdown.Option(key,value) for key,value in role_names.items()]
        accounts=list_users(current_user['value']['id'])
        rows=[]
        for account in accounts:
            is_current=account['id']==current_user['value']['id']
            def change_role(e,account_id=account['id']):
                try:
                    update_role(account_id,e.control.value,current_user['value']['id'])
                    notify('Đã cập nhật vai trò.')
                except ValueError as exc:
                    notify(str(exc),RED)
                    navigate(6)
            def change_active(e,account_id=account['id']):
                try:
                    update_active(account_id,e.control.value,current_user['value']['id'])
                    notify('Đã cập nhật trạng thái tài khoản.')
                except ValueError as exc:
                    notify(str(exc),RED)
                    navigate(6)
            rows.append(ft.Container(padding=12,
                border=ft.border.only(bottom=ft.BorderSide(1,BORDER)),
                content=ft.Row([
                    ft.Column([label(account['display_name'],13,WHITE,True),
                        label(account['email'] or account.get('phone') or
                            'Chưa có thông tin liên hệ',11)],spacing=3,expand=True),
                    ft.Dropdown(width=175,dense=True,value=account['role'],
                        options=role_options,disabled=is_current,on_change=change_role),
                    ft.Row([label('Đang hoạt động' if account['active'] else 'Đã khóa',10),
                        ft.Switch(value=account['active'],disabled=is_current,
                            on_change=change_active)],spacing=5)
                ],spacing=12)))
        return [ft.Row([ft.Column([
                    label('ADMINISTRATION',10,CYAN,True),
                    label('Quản lý tài khoản',23,WHITE,True),
                    label('Tạo tài khoản mới ở màn hình đăng ký; phân quyền hoặc khóa tài khoản tại đây.',11)
                ],spacing=4),ft.Container(expand=True),
                ft.TextButton('LÀM MỚI',icon=ft.Icons.REFRESH,on_click=lambda _:navigate(6))]),
            block([ft.Row([label('TÀI KHOẢN',10,CYAN,True),ft.Container(expand=True),
                    label(f'{len(accounts)} tài khoản',11,MUTED)]),
                *(rows or [label('Chưa có tài khoản.',12)])],padding=10)]

    sections=[dashboard,analysis,history_view,dataset,training,model,accounts_view,support_view]
    page_names=[*PAGES,('Quản lý tài khoản',ft.Icons.MANAGE_ACCOUNTS_ROUNDED),
        ('Hỗ trợ',ft.Icons.SUPPORT_AGENT)]
    page_subtitles=['RESEARCH COMMAND CENTER','IMAGE INFERENCE WORKSTATION','SQL SERVER INSPECTION LOG',
        'DATASET INTELLIGENCE','TRAINING METRICS','AI MODEL CONFIGURATION','ACCOUNT ADMINISTRATION',
        'SUPPORT CENTER']
    def update_result_badge():
        badge=result_badge['control']
        if badge is None or current_user['value'] is None:
            return
        try:
            count=unseen_result_count(current_user['value']['id'])
        except Exception:
            logger.warning('Could not refresh result badge',exc_info=True)
            return
        badge.visible=count>0
        badge.content.value=str(count) if count<100 else '99+'

    def update_support_badge():
        badge=support_badge['control']
        if badge is None or current_user['value'] is None:
            return
        user=current_user['value']
        try:
            count=support_unread_count(user['id'],user['role'])
        except Exception:
            logger.warning('Could not refresh support badge',exc_info=True)
            return
        badge.visible=count>0
        badge.content.value=str(count) if count<100 else '99+'

    async def poll_support_badge():
        while session_alive['value']:
            await asyncio.sleep(5)
            user=current_user['value']
            badge=support_badge['control']
            if user is None or badge is None:
                continue
            user_id=user['id']
            role=user['role']
            try:
                count=await asyncio.to_thread(support_unread_count,user_id,role)
            except Exception:
                logger.debug('Could not refresh support badge',exc_info=True)
                continue
            if (not session_alive['value'] or current_user['value'] is None
                    or current_user['value']['id']!=user_id
                    or support_badge['control'] is not badge):
                continue
            badge.visible=count>0
            badge.content.value=str(count) if count<100 else '99+'
            if active_page['index']==7 and selected_support['thread_id'] is not None:
                try:
                    threads=await asyncio.to_thread(support_threads,user_id,role)
                    thread=next((item for item in threads
                        if item['id']==selected_support['thread_id']),None)
                except Exception:
                    logger.debug('Could not refresh active support thread',exc_info=True)
                else:
                    latest_status=thread['status'] if thread else None
                    latest_updated_at=thread['updated_at'] if thread else None
                    if (latest_status!=selected_support['status']
                            or latest_updated_at!=selected_support['updated_at']):
                        navigate(7)
                        continue
            try:
                page.update()
            except RuntimeError:
                session_alive['value']=False
                logger.debug('Support polling stopped after page disconnect',exc_info=True)
                return

    async def prewarm_ai_runtime():
        try:
            timings=await asyncio.to_thread(prewarm_ai_worker)
            logger.info('AI runtime prewarmed: %s',timings)
        except Exception:
            logger.warning('AI runtime prewarm failed',exc_info=True)

    def navigate(index):
        if current_user['value'] is None:
            show_auth()
            return
        try:
            fresh=refresh_session(current_user['value'],current_account)
        except Exception:
            logger.exception('Session refresh failed')
            current_user['value']=None
            auth_state['message']='Mất kết nối LocalDB. Hãy kiểm tra dịch vụ rồi đăng nhập lại.'
            auth_state['message_error']=True
            show_auth()
            return
        if fresh is None:
            logout()
            auth_state['message']='Phiên đăng nhập đã thay đổi. Hãy đăng nhập lại.'
            auth_state['message_error']=True
            show_auth()
            return
        current_user['value']=fresh
        role=fresh['role']
        allowed_pages=ROLE_PAGES[role]
        if index not in allowed_pages:
            notify('Bạn không có quyền mở mục này.',RED)
            return
        active_page['index']=index
        page_title.value=page_names[index][0]
        page_title.color=WHITE
        subtitle.value=page_subtitles[index]
        subtitle.color=CYAN
        try:
            section_controls=sections[index]()
        except Exception:
            logger.exception('Failed to build page index=%s role=%s',index,role)
            section_controls=[block([
                ft.Icon(ft.Icons.ERROR_OUTLINE,color=RED,size=42),
                label('Không thể tải màn hình này.',18,WHITE,True),
                label('Hãy kiểm tra kết nối LocalDB rồi thử lại. Chi tiết kỹ thuật đã được ghi vào logs/pigskin.log.',11),
                ft.ElevatedButton('THỬ LẠI',icon=ft.Icons.REFRESH,
                    on_click=lambda _,retry_index=index:navigate(retry_index),
                    bgcolor=CYAN,color=BG)
            ],padding=20)]
        workspace_body.content=ft.Column(section_controls,expand=True,
            scroll=ft.ScrollMode.AUTO,spacing=17)
        for page_index,b in zip(nav_page_indexes,nav):
            selected_page=page_index==index
            b.bgcolor=NAV_SELECTED if selected_page else SIDEBAR
            b.content.controls[0].color=CYAN if selected_page else MUTED
            if len(b.content.controls)>1:
                b.content.controls[1].color=WHITE if selected_page else MUTED
        if index==2 and role=='user':
            update_result_badge()
        update_support_badge()
        page.update()
    def toggle_theme(e):
        theme_choice['value']='light' if theme_choice['value']=='dark' else 'dark'
        render_shell(active_page['index'])
    def toggle_sidebar(e):
        sidebar_collapsed['value']=not sidebar_collapsed['value']
        render_shell(active_page['index'])
    def render_shell(index):
        apply_palette(theme_choice['value'])
        page.bgcolor=BG
        page.theme_mode=ft.ThemeMode.LIGHT if theme_choice['value']=='light' else ft.ThemeMode.DARK
        page.theme=ft.Theme(color_scheme_seed=BLUE)
        page_title.color=WHITE;subtitle.color=CYAN
        file_line.color=MUTED;case_identifier.color=WHITE;case_state.color=AMBER
        received_at_label.color=WHITE;entered_at_label.color=TEAL
        noimage.controls[0].color=CYAN;noimage.controls[1].color=WHITE;noimage.controls[2].color=MUTED
        preview_frame.bgcolor=INNER;preview_frame.border=ft.border.all(1,BORDER)
        if notice.value.startswith(('Ảnh hợp lệ','Đã lưu hồ sơ')):
            notice.color=TEAL
        elif notice.value.startswith('Lỗi:'):
            notice.color=RED
        else:
            notice.color=AMBER
        nav.clear()
        nav_page_indexes.clear()
        support_badge['control']=None
        role=current_user['value']['role']
        visible_pages=[(index,*page_names[index]) for index in ROLE_PAGES[role]]
        compact=sidebar_collapsed['value']
        for idx,name,icon in visible_pages:
            nav_page_indexes.append(idx)
            controls=[ft.Icon(icon,size=19,color=MUTED)]
            if not compact:
                controls.extend([label(name,13,MUTED,True),ft.Container(expand=True)])
            if idx==7:
                try:
                    unread=support_unread_count(current_user['value']['id'],role)
                except Exception:
                    logger.warning('Could not load initial support badge',exc_info=True)
                    unread=0
                badge=ft.Container(bgcolor=RED,border_radius=10,width=19,height=19,
                    alignment=ft.alignment.center,visible=unread>0,
                    content=label(str(unread) if unread<100 else '99+',9,WHITE,True))
                support_badge['control']=badge
                controls.append(badge)
            nav.append(ft.Container(ink=True,bgcolor=SIDEBAR,padding=6 if compact else 13,border_radius=9,
                tooltip=name,
                on_click=lambda e,i=idx:navigate(i),content=ft.Row(controls,spacing=4 if compact else 13)))
        sidebar=ft.Container(width=78 if compact else 244,bgcolor=SIDEBAR,padding=12 if compact else 18,content=ft.Column([
            ft.Row([ft.Container(bgcolor=CYAN,padding=11,border_radius=9,
                content=ft.Icon(ft.Icons.MONITOR_HEART,color=BG,size=26)),
                *([] if compact else [ft.Column([label('PigSkin AI',19,WHITE,True),label('RESEARCH STUDIO',10,CYAN,True)],spacing=2)])]),
            ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT if compact else ft.Icons.CHEVRON_LEFT,
                tooltip='Mở rộng menu' if compact else 'Thu gọn menu',on_click=toggle_sidebar),
            ft.Container(height=8),
            *([] if compact else [label('DANH MỤC HỆ THỐNG',10,CYAN,True)]),
            ft.Column(nav,spacing=6),ft.Container(expand=True),
            *([] if compact else [ft.Container(bgcolor=PANEL,border_radius=10,padding=13,content=ft.Column([
                label('SYSTEM STATUS',11,CYAN,True),label('● Flet Desktop',11,TEAL),
                label('● SQL Server LocalDB',11,TEAL),
                label('● '+('Model files detected' if model_ready() else 'Awaiting AI weights'),11,AMBER)])),
            label('© 2026 • Nam / devN',10)])],expand=True))
        theme_button=ft.IconButton(icon=ft.Icons.LIGHT_MODE if theme_choice['value']=='dark' else ft.Icons.DARK_MODE,
            tooltip='Chuyển sang giao diện sáng' if theme_choice['value']=='dark' else 'Chuyển sang giao diện tối',
            on_click=toggle_theme)
        header_controls=[ft.Column([subtitle,page_title],spacing=4),ft.Container(expand=True)]
        if role=='user':
            try:
                unseen=unseen_result_count(current_user['value']['id'])
            except Exception:
                logger.warning('Could not load initial result badge',exc_info=True)
                unseen=0
            badge=ft.Container(bgcolor=RED,border_radius=10,width=19,height=19,
                alignment=ft.alignment.center,visible=unseen>0,
                content=label(str(unseen) if unseen<100 else '99+',9,WHITE,True))
            result_badge['control']=badge
            header_controls.append(ft.Row([
                ft.IconButton(icon=ft.Icons.NOTIFICATIONS_ACTIVE if unseen else ft.Icons.NOTIFICATIONS_NONE,
                    tooltip='Kết quả đã trả • mở lịch sử',on_click=lambda _:navigate(2)),
                badge],spacing=1))
        else:
            result_badge['control']=None
        header_controls.extend([theme_button,
            ft.Container(bgcolor=CHIP_BG,border_radius=8,padding=10,content=label(
                f"{current_user['value']['display_name']} • "+
                {'user':'NGƯỜI DÙNG','expert':'CHUYÊN GIA','admin':'QUẢN TRỊ'}[role],
                10,CYAN,True)),
            ft.IconButton(icon=ft.Icons.LOGOUT,tooltip='Đăng xuất',on_click=logout)])
        header=ft.Container(bgcolor=HEADER_BG,padding=ft.padding.symmetric(horizontal=25,vertical=18),
            border=ft.border.only(bottom=ft.BorderSide(1,BORDER)),
            content=ft.Row(header_controls))
        page.floating_action_button=ft.FloatingActionButton(
            icon=ft.Icons.SUPPORT_AGENT,text='Hỗ trợ',
            on_click=lambda _:navigate(7),bgcolor=CYAN,foreground_color=BG)
        workspace=ft.Column([header,workspace_body],expand=True,spacing=0)
        page.controls.clear()
        page.add(ft.Row([sidebar,ft.Container(content=workspace,expand=True)],spacing=0,expand=True))
        navigate(index)

    auth_state={
        'mode':'login','method':'password','channel':'email','step':'form',
        'challenge_id':None,'contact':'','display_name':'','password':'',
        'confirm_password':'','new_password':'','code':'','show_password':False,
        'loading':False,'message':'','message_error':True,
    }

    def logout(e=None):
        current_user['value']=None
        selected.update(path=None,info=None,result=None,record_id=None)
        selected_support.update(thread_id=None,status=None,updated_at=None)
        auth_state.update(
            mode='login',method='password',channel='email',step='form',
            challenge_id=None,contact='',display_name='',password='',
            confirm_password='',new_password='',code='',show_password=False,
            loading=False,message='',message_error=True,
        )
        reset_case_context()
        preview_frame.content=noimage
        image.visible=False
        image.src_base64=None
        file_line.value='Chưa chọn ảnh'
        notice.value='AI chưa sẵn sàng. Bạn có thể kiểm tra ảnh và lưu lịch sử.'
        notice.color=AMBER
        show_auth()
    async def submit_auth(e):
        if auth_state['loading']:
            return
        auth_state['loading']=True
        auth_state['message']=''
        show_auth()
        try:
            user=await asyncio.to_thread(
                authenticate,auth_state['contact'],auth_state['password']
            )
            if user is None:
                auth_state['message']=(
                    'Email hoặc mật khẩu không chính xác, hoặc tài khoản đã bị khóa.'
                )
                auth_state['message_error']=True
                return
            current_user['value']=user
            auth_state['password']=''
            auth_state['confirm_password']=''
            render_shell(0)
            if hasattr(page,'run_task'):
                background_tasks.append(page.run_task(prewarm_ai_runtime))
        except ValueError as exc:
            auth_state['message']=str(exc)
            auth_state['message_error']=True
        except Exception as exc:
            logger.error('Authentication flow failed (%s)',type(exc).__name__)
            auth_state['message']=(
                'Không thể xác thực lúc này. Vui lòng kiểm tra kết nối LocalDB.'
            )
            auth_state['message_error']=True
        finally:
            auth_state['loading']=False
            if current_user['value'] is None:
                show_auth()

    async def create_unverified_account(e):
        if auth_state['loading']:
            return
        auth_state['loading']=True
        auth_state['message']=''
        show_auth()
        try:
            if auth_state['mode'] != 'register':
                raise ValueError('Hãy mở màn hình tạo tài khoản trước.')
            if auth_state['channel'] != 'email':
                raise ValueError(
                    'Tạo tài khoản không cần mã hiện chỉ hỗ trợ email. Hãy chọn Email.'
                )
            if not auth_state['display_name'].strip():
                raise ValueError('Vui lòng nhập họ và tên.')
            password=auth_state['password']
            if not 8 <= len(password) <= 128:
                raise ValueError('Mật khẩu cần dài từ 8 đến 128 ký tự.')
            if password != auth_state['confirm_password']:
                raise ValueError('Mật khẩu nhập lại không khớp.')
            user=await asyncio.to_thread(
                register_unverified_email,auth_state['contact'],password,
                auth_state['display_name']
            )
            current_user['value']=user
            auth_state['password']=''
            auth_state['confirm_password']=''
            auth_state['message']=''
            render_shell(0)
            if hasattr(page,'run_task'):
                background_tasks.append(page.run_task(prewarm_ai_runtime))
        except ValueError as exc:
            auth_state['message']=str(exc)
            auth_state['message_error']=True
        except Exception as exc:
            logger.error('Unverified account creation failed (%s)',type(exc).__name__)
            auth_state['message']=(
                'Không thể tạo tài khoản lúc này. Vui lòng kiểm tra kết nối LocalDB.'
            )
            auth_state['message_error']=True
        finally:
            auth_state['loading']=False
            if current_user['value'] is None:
                show_auth()

    async def request_auth_code(e):
        if auth_state['loading']:
            return
        auth_state['loading']=True
        auth_state['message']=''
        show_auth()
        mode=auth_state['mode']
        channel=auth_state['channel']
        purpose={
            'login':'login','register':'registration','forgot':'password_reset'
        }[mode]
        reset_response=(
            'Nếu thông tin khớp tài khoản đã xác minh, yêu cầu sẽ được xử lý. '
            'Nếu chưa nhận mã, hãy kiểm tra kết nối dịch vụ và thử lại sau.'
        )
        try:
            destination=normalize_contact(auth_state['contact'],channel)
            if mode=='register':
                if not auth_state['display_name'].strip():
                    raise ValueError('Vui lòng nhập họ và tên.')
                password=auth_state['password']
                if not 8 <= len(password) <= 128:
                    raise ValueError('Mật khẩu cần dài từ 8 đến 128 ký tự.')
                if password != auth_state['confirm_password']:
                    raise ValueError('Mật khẩu nhập lại không khớp.')
            otp_service=OTPService(channel,configured_provider(channel))
            if not await asyncio.to_thread(otp_schema_ready):
                raise OTPMigrationRequiredError(
                    'OTP cần được bật bằng migration đã được phê duyệt.'
                )
            if mode=='register':
                exists=await asyncio.to_thread(contact_exists,destination,channel)
                if exists:
                    raise ValueError('Thông tin liên hệ này đã được đăng ký.')
            elif mode in {'login','forgot'}:
                contact_lookup=(
                    find_contact_for_password_reset
                    if mode=='forgot' else find_verified_contact
                )
                account=await asyncio.to_thread(contact_lookup,destination,channel)
                if account is None:
                    if mode=='forgot':
                        auth_state['step']='verify'
                        auth_state['code']=''
                        auth_state['message']=reset_response
                        auth_state['message_error']=False
                        return
                    raise ValueError(
                        'Thông tin không khớp tài khoản đã xác minh hoặc tài khoản đã bị khóa.'
                    )
            challenge_id=await asyncio.to_thread(
                otp_service.request_code,destination,purpose
            )
            auth_state['challenge_id']=challenge_id
            auth_state['step']='verify'
            auth_state['code']=''
            auth_state['message']=(
                reset_response if mode=='forgot' else
                'Dịch vụ gửi mã đã chấp nhận yêu cầu. Hãy kiểm tra hộp thư hoặc tin nhắn.'
            )
            auth_state['message_error']=False
        except OTPError as exc:
            if mode=='forgot':
                if isinstance(exc,OTPNotConfiguredError):
                    auth_state['message']='Chưa cấu hình dịch vụ gửi mã. '+reset_response
                elif isinstance(exc,OTPMigrationRequiredError):
                    auth_state['message']=(
                        'OTP chưa sẵn sàng: cần áp dụng migration sau khi được phê duyệt. '
                        +reset_response
                    )
                else:
                    auth_state['step']='verify'
                    logger.warning(
                        'Password reset OTP request failed (%s)',type(exc).__name__
                    )
                    auth_state['message']=reset_response
                auth_state['message_error']=False
            else:
                auth_state['message']=str(exc)
                auth_state['message_error']=True
        except ValueError as exc:
            auth_state['message']=str(exc)
            auth_state['message_error']=True
        except Exception as exc:
            logger.error('OTP request failed (%s)',type(exc).__name__)
            if mode=='forgot':
                auth_state['step']='verify'
            auth_state['message']=(
                reset_response if mode=='forgot' else
                'Không thể gửi mã lúc này. Kiểm tra cấu hình dịch vụ và kết nối.'
            )
            auth_state['message_error']=mode!='forgot'
        finally:
            auth_state['loading']=False
            show_auth()

    async def resend_auth_code(e):
        await request_auth_code(e)

    async def verify_auth_code(e):
        if auth_state['loading']:
            return
        auth_state['loading']=True
        auth_state['message']=''
        show_auth()
        mode=auth_state['mode']
        channel=auth_state['channel']
        purpose={
            'login':'login','register':'registration','forgot':'password_reset'
        }[mode]
        try:
            if mode=='forgot':
                password=auth_state['new_password']
                if not 8 <= len(password) <= 128:
                    raise ValueError('Mật khẩu mới cần dài từ 8 đến 128 ký tự.')
                if password != auth_state['confirm_password']:
                    raise ValueError('Mật khẩu mới nhập lại không khớp.')
            elif mode=='register':
                password=auth_state['password']
                if not 8 <= len(password) <= 128:
                    raise ValueError('Mật khẩu cần dài từ 8 đến 128 ký tự.')
                if password != auth_state['confirm_password']:
                    raise ValueError('Mật khẩu nhập lại không khớp.')
            otp_service=OTPService(channel,configured_provider(channel))
            verified=await asyncio.to_thread(
                otp_service.verify_code,auth_state['challenge_id'],
                auth_state['contact'],purpose,auth_state['code']
            )
            if mode=='login':
                user=await asyncio.to_thread(
                    authenticate_otp,auth_state['contact'],channel
                )
                if user is None:
                    raise ValueError(
                        'Tài khoản không còn hoạt động. Vui lòng đăng nhập lại.'
                    )
                current_user['value']=user
                auth_state['password']=''
                auth_state['code']=''
                render_shell(0)
                if hasattr(page,'run_task'):
                    background_tasks.append(page.run_task(prewarm_ai_runtime))
            elif mode=='register':
                email=verified['destination'] if channel=='email' else None
                phone=verified['destination'] if channel=='sms' else None
                user=await asyncio.to_thread(
                    register,email,auth_state['password'],
                    auth_state['display_name'],phone,verified
                )
                current_user['value']=user
                auth_state['password']=''
                auth_state['confirm_password']=''
                auth_state['code']=''
                render_shell(0)
                if hasattr(page,'run_task'):
                    background_tasks.append(page.run_task(prewarm_ai_runtime))
            else:
                await asyncio.to_thread(
                    reset_password,verified['destination'],channel,
                    auth_state['new_password'],verified
                )
                auth_state.update(
                    mode='login',method='password',channel='email',step='form',
                    challenge_id=None,contact='',password='',new_password='',
                    confirm_password='',code='',
                )
                auth_state['message']='Mật khẩu đã được cập nhật. Bạn có thể đăng nhập.'
                auth_state['message_error']=False
        except (OTPError,ValueError) as exc:
            auth_state['message']=str(exc)
            auth_state['message_error']=True
        except Exception as exc:
            logger.error('OTP verification failed (%s)',type(exc).__name__)
            auth_state['message']=(
                'Không thể xác minh lúc này. Vui lòng kiểm tra kết nối LocalDB.'
            )
            auth_state['message_error']=True
        finally:
            auth_state['loading']=False
            if current_user['value'] is None:
                show_auth()

    def show_auth():
        try:
            account_count()
        except Exception:
            logger.exception('Could not read account state')
            auth_state['message']=(
                'Không thể kết nối SQL Server LocalDB. Kiểm tra LocalDB và ODBC Driver.'
            )
            auth_state['message_error']=True
        page.controls.clear()
        page.floating_action_button=None
        page.add(build_auth_view(auth_state,{
            'render':show_auth,'submit':submit_auth,
            'register_unverified':create_unverified_account,
            'request':request_auth_code,'verify':verify_auth_code,
            'resend':resend_auth_code,
        }))
        page.update()

    show_auth()
    if hasattr(page,'run_task'):
        background_tasks.append(page.run_task(poll_support_badge))

if __name__=='__main__':
    configure_logging()
    ft.app(target=main)
