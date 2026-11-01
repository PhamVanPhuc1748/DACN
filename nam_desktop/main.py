"""PigSkin AI Studio - original desktop research dashboard (Flet 0.28.3)."""
import base64
from collections import Counter
from datetime import datetime
import importlib.util
import json
import flet as ft
from pathlib import Path
from services.inference import inspect_image,predict,model_ready,WEIGHTS,CLASSES
from services.store import recent,save,delete,update_review,update_case

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
    page.title='PigSkin AI Studio — Desktop Research'; page.padding=0;page.spacing=0
    page.bgcolor=BG; page.theme_mode=ft.ThemeMode.DARK
    page.window.width=1510;page.window.height=920;page.window.min_width=1000;page.window.min_height=690
    page.theme=ft.Theme(color_scheme_seed=BLUE)
    selected={'path':None,'info':None,'result':None,'record_id':None}
    page_title=label('Tổng quan',25,WHITE,True)
    subtitle=label('TRUNG TÂM NGHIÊN CỨU • PHÁT HIỆN BỆNH DA HEO',10,CYAN,True)
    body=ft.Column(expand=True,scroll=ft.ScrollMode.AUTO,spacing=17)
    nav=[]
    active_page={'index':0}
    theme_choice={'value':'dark'}

    def notify(message,color=CYAN):
        page.snack_bar=ft.SnackBar(content=label(message,13,WHITE),bgcolor=PANEL)
        page.snack_bar.open=True;page.update()

    def dashboard():
        rows=recent()
        pending=sum(1 for item in rows if (item.get('review_status') or 'needs_review')=='needs_review')
        inferred_rows=[item for item in rows if item['mode']=='ai' and item.get('predicted_class')]
        inferred=len(inferred_rows)
        class_counts=Counter(item['predicted_class'] for item in inferred_rows)
        header=ft.Container(bgcolor=HEADER_BG,border=ft.border.all(1,BORDER),border_radius=8,padding=13,
            content=ft.Row([ft.Column([label('PIGSKIN RESEARCH / OPERATIONS',10,CYAN,True),
                label('Điều phối ca nghiên cứu',21,WHITE,True),
                label('Tổng hợp hoạt động tiếp nhận, rà soát và kết quả thực nghiệm.',11)],spacing=4,expand=True),
                ft.Container(bgcolor=CHIP_BG,padding=9,border_radius=6,
                    content=label('CHECKPOINT ĐÃ PHÁT HIỆN' if model_ready() else 'ĐANG CHỜ CHECKPOINT',10,AMBER,True)),
                ft.ElevatedButton('TIẾP NHẬN CA',icon=ft.Icons.ADD,on_click=lambda _:navigate(1),bgcolor=CYAN,color=BG)]))
        stats=ft.Row([kpi('Hồ sơ gần đây',str(len(rows)),ft.Icons.FOLDER_OUTLINED,CYAN,'Tối đa 300 hồ sơ trong danh sách'),
            kpi('Chờ rà soát',str(pending),ft.Icons.HISTORY,AMBER,'Cần chuyên gia xác minh'),
            kpi('Có kết quả AI',str(inferred),ft.Icons.AUTO_AWESOME,TEAL,'Số hồ sơ chạy được checkpoint'),
            kpi('Ảnh dataset','2.017',ft.Icons.IMAGE_OUTLINED,BLUE,'Số liệu báo cáo của nhóm')],spacing=10)
        queue_lines=[]
        review_labels={'needs_review':'CHỜ RÀ SOÁT','reviewed':'ĐÃ RÀ SOÁT',
                       'lab_requested':'CẦN XÉT NGHIỆM','closed':'ĐÃ ĐÓNG'}
        for item in rows[:6]:
            status=item.get('review_status') or 'needs_review'
            prediction=item['predicted_class'] or 'Chưa có dự đoán AI'
            confidence=f" • {item['confidence']*100:.1f}% softmax" if item['confidence'] is not None else ''
            context=' • '.join(value for value in (item.get('farm_name'),item.get('body_site')) if value)
            queue_lines.append(ft.Container(padding=9,border=ft.border.only(bottom=ft.BorderSide(1,BORDER)),
                content=ft.Row([ft.Column([label(f"{item.get('case_id') or 'Hồ sơ cũ'}  /  {item.get('animal_id') or 'Chưa gắn mã cá thể'}",12,CYAN,True),
                    label(f"{item['filename']} • {context or 'Chưa có thông tin vị trí/cơ sở'}",10),
                    label(f"{prediction}{confidence}",11,WHITE)],spacing=3,expand=True),
                    label(review_labels.get(status,'CHỜ RÀ SOÁT'),9,AMBER if status=='needs_review' else TEAL,True)])))
        cases=block([ft.Row([caption_head('Hàng đợi hồ sơ','Sắp xếp mới nhất • trạng thái rà soát',ft.Icons.VIEW_LIST),
                    ft.Container(expand=True),ft.TextButton('MỞ LỊCH SỬ',on_click=lambda _:navigate(2))]),
                    *(queue_lines or [label('Chưa có hồ sơ. Tạo ca đầu tiên từ màn hình Phân tích ảnh.',12)]),
                    ft.TextButton('TIẾP NHẬN ẢNH MỚI',icon=ft.Icons.ADD_A_PHOTO,on_click=lambda _:navigate(1))],expand=3,padding=14)
        system=block([caption_head('Trạng thái hệ thống','Tình trạng tích hợp hiện tại',ft.Icons.HUB),
            ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE,color=TEAL,size=17),label('Flet desktop',11,WHITE,True)]),
            ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE,color=TEAL,size=17),label('SQLite local',11,WHITE,True)]),
            ft.Row([ft.Icon(ft.Icons.WARNING_AMBER,color=AMBER,size=17),
                label('Checkpoint và class map' if model_ready() else 'Chưa có trọng số AI',11,AMBER,True)]),
            label('Phát hiện đủ file chưa đồng nghĩa checkpoint tương thích.',10),
            ft.Divider(color=BORDER),label('Phân loại toàn ảnh • MobileNetV2',10,WHITE),
            label('Chưa có detection box hoặc heatmap.',10)],expand=2,padding=14)
        split=block([caption_head('Cấu trúc dataset','Số liệu nhóm cung cấp • chưa đồng bộ manifest',ft.Icons.DONUT_LARGE),
            meter('Train • 1.576 ảnh',1576/2017,BLUE,'78,1%'),
            meter('Validation • 240 ảnh',240/2017,AMBER,'11,9%'),
            meter('Test • 201 ảnh',201/2017,TEAL,'10,0%'),
            label('Chưa có thống kê theo từng lớp trong ứng dụng.',10,AMBER)],expand=1,padding=14)
        evaluation=block([caption_head('Kết quả thực nghiệm','Run 20261028_190505 • không phải dự đoán ca',ft.Icons.ANALYTICS),
            meter('Validation Macro-F1',.7100,BLUE),meter('Test Macro-F1',.6125,TEAL),
            meter('Test Accuracy',.6219,AMBER),
            label('Chưa có confusion matrix, precision/recall theo lớp hoặc log từng epoch.',10,AMBER)],expand=1,padding=14)
        if class_counts:
            ranked=class_counts.most_common()
            chart_width=max(420,min(900,page.window.width-510))
            chart=ft.BarChart(bar_groups=[ft.BarChartGroup(x=index,bar_rods=[ft.BarChartRod(
                    from_y=0,to_y=count/inferred*100,width=24,
                    color=[CYAN,BLUE,TEAL,AMBER][index%4],border_radius=3,
                    tooltip=f'{name}: {count} hồ sơ ({count/inferred*100:.1f}%)')])
                    for index,(name,count) in enumerate(ranked)],
                min_y=0,max_y=100,width=chart_width,height=270,groups_space=12,
                left_axis=ft.ChartAxis(labels=[ft.ChartAxisLabel(value=value,
                    label=label(f'{value}%',9,MUTED)) for value in (0,25,50,75,100)],labels_size=34),
                bottom_axis=ft.ChartAxis(labels=[ft.ChartAxisLabel(value=index,label=label(
                    name if len(name)<=10 else name[:9]+'..',9,MUTED)) for index,(name,_) in enumerate(ranked)],
                    labels_size=42),
                horizontal_grid_lines=ft.ChartGridLines(interval=25,color=BORDER,width=1),
                tooltip_bgcolor=SIDEBAR,interactive=True)
            distribution_content=ft.Column([chart,label(
                f'Top-1 trên {inferred} hồ sơ AI trong tối đa 300 hồ sơ mới nhất; không phải tỷ lệ mắc bệnh.',10,AMBER)],spacing=4)
        else:
            distribution_content=ft.Container(height=270,alignment=ft.alignment.center,
                content=ft.Column([ft.Icon(ft.Icons.BAR_CHART,size=42,color=MUTED),
                    label('Chưa có hồ sơ chạy AI để lập biểu đồ.',12,WHITE,True),
                    label('Cần checkpoint tương thích và class map thật.',10)],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,alignment=ft.MainAxisAlignment.CENTER,spacing=7))
        distribution=block([caption_head('Phân bố nhãn AI','Tần suất lớp đứng đầu trên các hồ sơ đã phân tích',ft.Icons.BAR_CHART),
            distribution_content],expand=1,padding=14)
        return [header,stats,ft.Row([distribution],spacing=10),
                ft.Row([cases,system],spacing=10,vertical_alignment=ft.CrossAxisAlignment.START),
                ft.Row([split,evaluation],spacing=10,vertical_alignment=ft.CrossAxisAlignment.START)]

    # Single picker registered once; reusable across visits.
    image=ft.Image(width=480,height=340,fit=ft.ImageFit.CONTAIN,visible=False)
    noimage=ft.Column([ft.Icon(ft.Icons.ADD_PHOTO_ALTERNATE_OUTLINED,size=57,color=CYAN),
        label('CHỌN ẢNH DA HEO',18,WHITE,True),label('JPG / PNG / WEBP • Tối đa 10 MB',12)],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,alignment=ft.MainAxisAlignment.CENTER)
    preview_frame=ft.Container(content=noimage,bgcolor=INNER,height=366,alignment=ft.alignment.center,
                               border=ft.border.all(1,BORDER),border_radius=12)
    file_line=label('Chưa chọn ảnh',12)
    notice=label('AI chưa sẵn sàng. Bạn có thể kiểm tra ảnh và lưu lịch sử.',12,AMBER)
    result_holder=ft.Column(spacing=13)
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
            image.src_base64=base64.b64encode(open(path,'rb').read()).decode('ascii')
            image.visible=True;preview_frame.content=image
            case_identifier.value='HỒ SƠ SẼ ĐƯỢC TẠO KHI KIỂM TRA'
            case_state.value='ẢNH ĐÃ NẠP • CHỜ PHÂN TÍCH'
            file_line.value=f"{info['name']} • {info['width']}×{info['height']} px • {info['bytes']/1048576:.2f} MB"
            notice.value='Ảnh hợp lệ, có thể bắt đầu kiểm tra.';notice.color=TEAL
            render_result();page.update()
        except (ValueError,OSError) as exc:
            notify(str(exc),RED)
    picker=ft.FilePicker(on_result=selected_file)
    page.overlay.append(picker)

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

    def process_image(e):
        if not selected['path']:
            notify('Bạn chưa chọn ảnh.');return
        if selected['record_id']:
            notify('Hồ sơ này đã được lưu. Chọn “Ca mới” để tiếp nhận ảnh khác.');return
        try:
            info=inspect_image(selected['path'])
            result=predict(selected['path'])
            case={'animal_id':animal_id_field.value or '', 'farm_name':farm_field.value or '',
                'body_site':body_site_field.value or '', 'onset_date':onset_field.value or '',
                'symptoms':symptoms_field.value or '', 'entered_at':entered_at['value']}
            rid=save(info,result,case,selected['path'])
            selected.update(info=info,result=result,record_id=rid)
            saved_record=next((item for item in recent() if item['id']==rid),None)
            case_identifier.value=f'PS-{rid:06d}'
            case_state.value='ĐÃ LƯU • CHỜ CHUYÊN GIA RÀ SOÁT'
            received_at_label.value=saved_record['created_at'] if saved_record else 'Đã lưu thời gian tiếp nhận'
            notice.value=f'Đã lưu hồ sơ PS-{rid:06d} vào SQLite.'; notice.color=TEAL
            render_result();page.update()
        except Exception as exc:
            notice.value=f'Lỗi: {exc}';notice.color=RED;page.update()

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
                        label('MobileNetV2 • 10 lớp • input 224×224',11,WHITE,True)]),
                    label('Checkpoint: '+('đã phát hiện file' if model_ready() else 'chưa tích hợp'),11,AMBER),
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
        term=ft.TextField(hint_text='Tìm mã ca, mã heo, cơ sở hoặc tên ảnh...',
                          prefix_icon=ft.Icons.SEARCH,expand=True,dense=True)
        rows_area=ft.Column(spacing=0)
        count=label('',13,CYAN,True)
        review_labels={'needs_review':'Chờ rà soát','reviewed':'Đã rà soát',
                       'lab_requested':'Cần xét nghiệm','closed':'Đã đóng'}
        review_filter=ft.Dropdown(width=180,dense=True,value='all',label='Trạng thái',
            options=[ft.dropdown.Option('all','Tất cả trạng thái'),
                     *[ft.dropdown.Option(key,text) for key,text in review_labels.items()]])
        def load(e=None):
            items=recent(term.value or '')
            if review_filter.value!='all':
                items=[item for item in items if (item.get('review_status') or 'needs_review')==review_filter.value]
            count.value=f'{len(items)} bản ghi phù hợp'
            rows_area.controls.clear()
            for it in items:
                scores=json.loads(it.get('scores_json') or '[]')
                prediction=it['predicted_class'] or 'Ảnh hợp lệ, chưa có AI'
                score_text=f" • {it['confidence']*100:.1f}% softmax" if it['confidence'] is not None else ''
                status=it.get('review_status') or 'needs_review'
                context=' • '.join(value for value in (it.get('farm_name'),it.get('body_site'),
                    f"Khởi phát: {it['onset_date']}" if it.get('onset_date') else '',
                    f"Nhập/cập nhật: {it['entered_at']}" if it.get('entered_at') else '') if value)
                symptoms=it.get('symptoms') or 'Chưa có mô tả quan sát'
                line=ft.Row([ft.Column([
                    label(f"{it['case_id'] or 'Hồ sơ cũ'} • {it['animal_id'] or 'Chưa gắn mã cá thể'}",12,CYAN,True),
                    label(f"{it['filename']} • Tiếp nhận: {it['created_at']}",10),
                    label(f"{context or 'Chưa có thông tin cơ sở/vị trí'}",10),
                    label(f"Mô tả: {symptoms}",10,WHITE),
                    label(f"{prediction}{score_text} • {len(scores)} lớp đã lưu",11,WHITE)],spacing=3,expand=True),
                    ft.IconButton(icon=ft.Icons.IMAGE_SEARCH,icon_color=TEAL,tooltip='Xem ảnh gốc',
                        disabled=not bool(it.get('image_path')),
                        on_click=lambda e,record=it:show_image(record)),
                    ft.IconButton(icon=ft.Icons.EDIT_OUTLINED,icon_color=BLUE,tooltip='Sửa hồ sơ',
                        on_click=lambda e,record=it:edit_case(record)),
                    ft.Dropdown(width=155,dense=True,value=status,
                        options=[ft.dropdown.Option(key,text) for key,text in review_labels.items()],
                        on_change=lambda e,record=it['id']:save_review(record,e.control.value)),
                    ft.IconButton(icon=ft.Icons.DELETE_OUTLINE,icon_color=RED,tooltip='Xóa bản ghi',
                        on_click=lambda e,record=it['id']:erase(record))],spacing=12)
                rows_area.controls.append(ft.Container(content=line,padding=10,
                   border=ft.border.only(bottom=ft.BorderSide(1,BORDER))))
            if not items:rows_area.controls.append(label('Chưa có lượt kiểm tra nào.',14))
            page.update()
        def erase(record):
            delete(record);load();notify('Đã xóa bản ghi.')
        def show_image(record):
            image_path=Path(record.get('image_path') or '')
            if not image_path.is_file():
                notify('Không tìm thấy ảnh đã lưu trong hồ sơ.',RED);return
            encoded=base64.b64encode(image_path.read_bytes()).decode('ascii')
            dialog=ft.AlertDialog(modal=True,title=label(f"Ảnh hồ sơ • {record['filename']}",16,WHITE,True),
                content=ft.Container(width=900,height=600,bgcolor=INNER,alignment=ft.alignment.center,
                    content=ft.Image(src_base64=encoded,fit=ft.ImageFit.CONTAIN)),
                actions=[ft.TextButton('Đóng',on_click=lambda e:page.close(dialog))],bgcolor=PANEL)
            page.open(dialog)
        def save_review(record,status):
            update_review(record,status)
            notify(f"Trạng thái: {review_labels.get(status,status)}")
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
                update_case(record['id'],{'animal_id':animal.value or '',
                    'farm_name':farm.value or '', 'body_site':site.value or '',
                    'onset_date':onset.value or '', 'symptoms':symptoms.value or '',
                    'entered_at':changed_at})
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
        term.on_change=load
        review_filter.on_change=load
        load()
        return [block([caption_head('Lịch sử kiểm tra ảnh','Ảnh gốc được lưu cục bộ cùng hồ sơ',ft.Icons.HISTORY),
                ft.Row([term,review_filter,ft.OutlinedButton('Làm mới',icon=ft.Icons.REFRESH,on_click=load)]),
                ft.Row([label('HỒ SƠ / QUAN SÁT / NHẬN ĐỊNH',10,CYAN,True),ft.Container(expand=True),
                    label('SỬA',10,BLUE,True),label('TRẠNG THÁI',10,CYAN,True),label('XÓA',10,RED,True)],spacing=12),count,
                ft.Container(content=rows_area,bgcolor=INNER,border_radius=10,padding=8)],padding=20)]

    def dataset():
        summary=ft.Row([kpi('Tổng ảnh','2.017',ft.Icons.IMAGE,BLUE,'Theo báo cáo nhóm'),
            kpi('Training','1.576',ft.Icons.SCHOOL,BLUE,'78,1% tổng dữ liệu'),
            kpi('Validation','240',ft.Icons.VERIFIED,AMBER,'11,9% tổng dữ liệu'),
            kpi('Testing','201',ft.Icons.FACT_CHECK,TEAL,'10,0% tổng dữ liệu')],spacing=10)
        split=block([caption_head('Phân chia tập','Tổng 2.017 ảnh • single-label',ft.Icons.DONUT_LARGE),
            meter('Train',1576/2017,BLUE,'1.576 ảnh'),meter('Validation',240/2017,AMBER,'240 ảnh'),
            meter('Test',201/2017,TEAL,'201 ảnh')],expand=1,padding=14)
        audit=block([caption_head('Dataset audit','Trạng thái tích hợp dữ liệu trong ứng dụng',ft.Icons.FACT_CHECK),
            ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE,color=TEAL,size=17),
                label('Tổng số ảnh và split có trong báo cáo nhóm',11,WHITE)]),
            ft.Row([ft.Icon(ft.Icons.WARNING_AMBER,color=AMBER,size=17),
                label('Manifest chưa được kết nối vào ứng dụng',11,AMBER)]),
            ft.Row([ft.Icon(ft.Icons.WARNING_AMBER,color=AMBER,size=17),
                label('Chưa có phân bố ảnh theo từng lớp ở đây',11,AMBER)]),
            ft.Row([ft.Icon(ft.Icons.INFO_OUTLINE,color=BLUE,size=17),
                label('Cần đối chiếu license, nhãn và trùng lặp tại nguồn dataset',11)]),
            label('Các thanh tỷ lệ chỉ trực quan hóa tổng số đã ghi nhận; không thay thế kiểm toán dữ liệu.',10)],
            expand=1,padding=14)
        return [ft.Row([ft.Column([label('DATASET INTELLIGENCE',10,CYAN,True),
                    label('Dataset profile',23,WHITE,True),
                    label('pig_skin_single_label_v4 • số liệu được ghi nhận, chưa đồng bộ manifest',11)],spacing=4),
                ft.Container(expand=True),label('SOURCE: BÁO CÁO NHÓM',10,AMBER,True)]),
            summary,ft.Row([split,audit],spacing=10,vertical_alignment=ft.CrossAxisAlignment.START)]

    def training():
        metrics=ft.Row([kpi('Best epoch','12',ft.Icons.TIMELINE,BLUE,'Run 20261028_190505'),
            kpi('Validation Macro-F1','0,7100',ft.Icons.ANALYTICS,TEAL,'Báo cáo nhóm'),
            kpi('Test Macro-F1','0,6125',ft.Icons.INSERT_CHART,BLUE,'Báo cáo nhóm'),
            kpi('Test Accuracy','62,19%',ft.Icons.TRACK_CHANGES,AMBER,'Báo cáo nhóm')],spacing=10)
        performance=block([caption_head('Hiệu năng được báo cáo','Không phải kết quả dự đoán của hồ sơ đang mở',ft.Icons.ANALYTICS),
            meter('Validation Macro-F1',.7100,BLUE),meter('Test Macro-F1',.6125,TEAL),
            meter('Test Accuracy',.6219,AMBER),
            label('Không suy ra precision, recall hoặc mAP từ các chỉ số trên.',10,AMBER)],expand=1,padding=14)
        reproducibility=block([caption_head('Experiment record','Thông tin cần có để tái lập và so sánh run',ft.Icons.SCIENCE_OUTLINED),
            ft.Row([label('Run ID',11),ft.Container(expand=True),label('20261028_190505',11,WHITE,True)]),
            ft.Row([label('Best epoch',11),ft.Container(expand=True),label('12',11,WHITE,True)]),
            ft.Row([label('Metric source',11),ft.Container(expand=True),label('Báo cáo nhóm',11,AMBER,True)]),
            ft.Divider(color=BORDER),
            label('Để so sánh đầy đủ cần cấu hình train, confusion matrix, precision/recall theo lớp và log từng epoch.',11),
            label('Trang này chỉ trình bày run đã ghi nhận; ứng dụng không huấn luyện mô hình.',10,AMBER)],expand=1,padding=14)
        return [ft.Row([ft.Column([label('TRAINING METRICS',10,CYAN,True),
                    label('Experiment review',23,WHITE,True),
                    label('Run đã ghi nhận • số liệu chưa liên kết file log trong ứng dụng',11)],spacing=4),
                ft.Container(expand=True),label('MODE: REPORT ONLY',10,AMBER,True)]),
            metrics,ft.Row([performance,reproducibility],spacing=10,vertical_alignment=ft.CrossAxisAlignment.START)]

    def model():
        def dependency_row(name,path,available):
            color=TEAL if available else AMBER
            icon=ft.Icons.CHECK_CIRCLE if available else ft.Icons.WARNING_AMBER
            state='ĐÃ PHÁT HIỆN' if available else 'CHƯA CÓ'
            return ft.Container(padding=9,border=ft.border.only(bottom=ft.BorderSide(1,BORDER)),
                content=ft.Row([ft.Icon(icon,color=color,size=17),
                    ft.Column([label(name,11,WHITE,True),label(path,10)],spacing=2,expand=True),
                    label(state,9,color,True)],spacing=10))
        checkpoint_exists=WEIGHTS.is_file()
        classes_exists=CLASSES.is_file()
        torch_exists=importlib.util.find_spec('torch') is not None
        torchvision_exists=importlib.util.find_spec('torchvision') is not None
        dependencies=block([caption_head('Runtime checklist','File tồn tại chưa chứng minh model tương thích',ft.Icons.FACT_CHECK),
            dependency_row('Checkpoint PyTorch','models/best.pth',checkpoint_exists),
            dependency_row('Thứ tự nhãn','models/classes.json',classes_exists),
            dependency_row('PyTorch','torch',torch_exists),
            dependency_row('TorchVision','torchvision',torchvision_exists),
            ft.Container(bgcolor=STATUS_BG,padding=10,border_radius=6,content=label(
                'Chỉ xác nhận sẵn sàng sau khi tải checkpoint thành công và kiểm tra trên tập ảnh độc lập.',10,AMBER))],
            expand=1,padding=14)
        specification=block([caption_head('Model specification','Pipeline hiện được code hỗ trợ',ft.Icons.MEMORY),
            ft.Row([label('Architecture',11),ft.Container(expand=True),label('MobileNetV2',11,WHITE,True)]),
            ft.Row([label('Classification classes',11),ft.Container(expand=True),label('10 (theo báo cáo)',11,WHITE,True)]),
            ft.Row([label('Input',11),ft.Container(expand=True),label('224 × 224 RGB',11,WHITE,True)]),
            ft.Row([label('Preprocessing',11),ft.Container(expand=True),label('Resize 256 → CenterCrop 224',10,WHITE,True)]),
            ft.Divider(color=BORDER),
            label('YOLO .pt cần adapter detection riêng; không thể đổi tên thành best.pth.',11,AMBER),
            label('Checkpoint là file trọng số đã học khi huấn luyện; nó không chứa dataset hay bảo đảm mô hình luôn đúng.',10),
            label('Chỉ phục vụ nghiên cứu, không thay thế đánh giá của bác sĩ thú y.',10)],expand=1,padding=14)
        overall='CẦN CÀI ĐỦ THÀNH PHẦN' if not (checkpoint_exists and classes_exists and torch_exists and torchvision_exists) else 'CẦN KIỂM TRA TƯƠNG THÍCH'
        return [ft.Row([ft.Column([label('AI MODEL CONFIGURATION',10,CYAN,True),
                    label('Model readiness',23,WHITE,True),
                    label('Trạng thái file và runtime • chưa thay thế validation model',11)],spacing=4),
                ft.Container(expand=True),ft.Container(bgcolor=STATUS_BG,padding=9,border_radius=6,
                    content=label(overall,10,AMBER,True))]),
            ft.Row([dependencies,specification],spacing=10,vertical_alignment=ft.CrossAxisAlignment.START)]

    sections=[dashboard,analysis,history_view,dataset,training,model]
    def navigate(index):
        active_page['index']=index
        page_title.value=PAGES[index][0]
        page_title.color=WHITE
        subtitle.value=['RESEARCH COMMAND CENTER','IMAGE INFERENCE WORKSTATION','SQLITE INSPECTION LOG',
               'DATASET INTELLIGENCE','TRAINING METRICS','AI MODEL CONFIGURATION'][index]
        subtitle.color=CYAN
        body.controls.clear();body.controls.extend(sections[index]())
        for n,b in enumerate(nav):
            b.bgcolor=NAV_SELECTED if n==index else SIDEBAR
            b.content.controls[0].color=CYAN if n==index else MUTED
            b.content.controls[1].color=WHITE if n==index else MUTED
        page.update()
    def toggle_theme(e):
        theme_choice['value']='light' if theme_choice['value']=='dark' else 'dark'
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
        for idx,(name,icon) in enumerate(PAGES):
            nav.append(ft.Container(ink=True,bgcolor=SIDEBAR,padding=13,border_radius=9,
                on_click=lambda e,i=idx:navigate(i),content=ft.Row([ft.Icon(icon,size=19,color=MUTED),
                    label(name,13,MUTED,True)],spacing=13)))
        sidebar=ft.Container(width=244,bgcolor=SIDEBAR,padding=18,content=ft.Column([
            ft.Row([ft.Container(bgcolor=CYAN,padding=11,border_radius=9,
                content=ft.Icon(ft.Icons.MONITOR_HEART,color=BG,size=26)),
                ft.Column([label('PigSkin AI',19,WHITE,True),label('RESEARCH STUDIO',10,CYAN,True)],spacing=2)]),
            ft.Container(height=20),label('DANH MỤC HỆ THỐNG',10,CYAN,True),
            ft.Column(nav,spacing=6),ft.Container(expand=True),
            ft.Container(bgcolor=PANEL,border_radius=10,padding=13,content=ft.Column([
                label('SYSTEM STATUS',11,CYAN,True),label('● Flet Desktop',11,TEAL),
                label('● SQLite Offline',11,TEAL),label('● '+('Model files detected' if model_ready() else 'Awaiting AI weights'),11,AMBER)])),
            label('© 2026 • Nam / devN',10)],expand=True))
        theme_button=ft.IconButton(icon=ft.Icons.LIGHT_MODE if theme_choice['value']=='dark' else ft.Icons.DARK_MODE,
            tooltip='Chuyển sang giao diện sáng' if theme_choice['value']=='dark' else 'Chuyển sang giao diện tối',
            on_click=toggle_theme)
        header=ft.Container(bgcolor=HEADER_BG,padding=ft.padding.symmetric(horizontal=25,vertical=18),
            border=ft.border.only(bottom=ft.BorderSide(1,BORDER)),content=ft.Row([
                ft.Column([subtitle,page_title],spacing=4),ft.Container(expand=True),theme_button,
                ft.Container(bgcolor=CHIP_BG,border_radius=8,padding=10,content=label(
                    '● FILE ĐÃ PHÁT HIỆN' if model_ready() else '● CHỜ CHECKPOINT',11,AMBER,True))]))
        workspace=ft.Column([header,ft.Container(content=body,padding=20,expand=True)],expand=True,spacing=0)
        page.controls.clear()
        page.add(ft.Row([sidebar,ft.Container(content=workspace,expand=True)],spacing=0,expand=True))
        navigate(index)
    render_shell(0)

if __name__=='__main__':
    ft.app(target=main)
