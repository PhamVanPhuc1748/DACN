"""PigSkin AI Studio - original desktop research dashboard (Flet 0.28.3)."""
import base64
import asyncio
from collections import Counter
from datetime import datetime
import json
import flet as ft
from pathlib import Path
from services.inference import inspect_image,predict,model_ready,model_status
from services.project_data import active_run,display_class
from services.store import recent,save,delete,update_review,update_case

PALETTES={
    'light':{'BG':'#E9EEE9','SIDEBAR':'#E9EEE9','PANEL':'#FFFFFF','INNER':'#F5F7F5',
        'BORDER':'#DDE4DE','PRIMARY':'#426A50','SLATE':'#496D7A','GREEN':'#34735D',
        'STRAW':'#85591F','PINK':'#A35F69','INK':'#202C24','QUIET':'#5D6B61','RED':'#A23F42',
        'BAR_BG':'#E7ECE8','HEADER_BG':'#E9EEE9','CHIP_BG':'#F5E9E9',
        'IMAGE_BG':'#F2F5F2','STATUS_BG':'#F5F0E5','NAV_SELECTED':'#DDE5DE'},
    'dark':{'BG':'#17211A','SIDEBAR':'#1B281F','PANEL':'#222E25','INNER':'#1C2920',
        'BORDER':'#34443A','PRIMARY':'#A0C5A6','SLATE':'#A2BECA','GREEN':'#85BBA1',
        'STRAW':'#E0BD7F','PINK':'#DEA0A7','INK':'#EFF3EE','QUIET':'#B4C0B6','RED':'#EF9698',
        'BAR_BG':'#35443A','HEADER_BG':'#1B281F','CHIP_BG':'#3A2C30',
        'IMAGE_BG':'#17211A','STATUS_BG':'#3A3528','NAV_SELECTED':'#2A3B30'},
}
BG=PALETTES['light']['BG']; SIDEBAR=PALETTES['light']['SIDEBAR']
PANEL=PALETTES['light']['PANEL']; INNER=PALETTES['light']['INNER']
BORDER=PALETTES['light']['BORDER']; PRIMARY=PALETTES['light']['PRIMARY']
SLATE=PALETTES['light']['SLATE']; GREEN=PALETTES['light']['GREEN']
STRAW=PALETTES['light']['STRAW']; PINK=PALETTES['light']['PINK']; INK=PALETTES['light']['INK']
QUIET=PALETTES['light']['QUIET']; RED=PALETTES['light']['RED']
BAR_BG=PALETTES['light']['BAR_BG']; HEADER_BG=PALETTES['light']['HEADER_BG']
CHIP_BG=PALETTES['light']['CHIP_BG']; IMAGE_BG=PALETTES['light']['IMAGE_BG']
STATUS_BG=PALETTES['light']['STATUS_BG']; NAV_SELECTED=PALETTES['light']['NAV_SELECTED']
PAGES=[('Tổng quan',ft.Icons.DASHBOARD_ROUNDED),('Phân tích ảnh',ft.Icons.IMAGE_SEARCH_ROUNDED),
       ('Lịch sử',ft.Icons.HISTORY_ROUNDED),('Dữ liệu',ft.Icons.STORAGE_ROUNDED),
       ('Huấn luyện',ft.Icons.QUERY_STATS_ROUNDED),('Mô hình AI',ft.Icons.PSYCHOLOGY_ROUNDED)]

def label(text,size=14,color=None,bold=False,**kw):
    color=QUIET if color is None else color
    return ft.Text(str(text),size=size,color=color,weight=ft.FontWeight.BOLD if bold else ft.FontWeight.NORMAL,**kw)

def block(children,padding=18,expand=None,**kw):
    return ft.Container(bgcolor=PANEL,border=ft.border.all(1,BORDER),border_radius=8,padding=padding,
        expand=expand,content=ft.Column(children,spacing=14),**kw)

def caption_head(title,sub=None,icon=None):
    return ft.Column([ft.Row(([ft.Icon(icon,color=PRIMARY,size=18)] if icon else [])+[label(title,16,INK,True)]),
                     *([label(sub,12)] if sub else [])],spacing=4)

def kpi(name,value,icon,color=None,sub=''):
    color=PRIMARY if color is None else color
    return ft.Container(expand=1,bgcolor=PANEL,padding=ft.padding.symmetric(horizontal=16,vertical=14),
         border=ft.border.only(right=ft.BorderSide(1,BORDER)),
         content=ft.Column([label(name,12,QUIET,True),label(value,28,INK),
            label(sub,11,color)],spacing=5))

def meter(name,value,color=None,caption=''):
    color=PRIMARY if color is None else color
    return ft.Column([ft.Row([label(name,12,INK),ft.Container(expand=True),label(f'{value*100:.1f}%',12,color,True)]),
        ft.ProgressBar(value=value,color=color,bgcolor=BAR_BG,bar_height=6),label(caption,11)],spacing=8)

def pig_mark(size=42):
    """Small pig-snout mark used as the app's subject-specific visual cue."""
    return ft.Container(width=size,height=size,bgcolor=CHIP_BG,border_radius=13,
        alignment=ft.alignment.center,
        content=ft.Container(width=29,height=19,bgcolor=PINK,border_radius=9,
            alignment=ft.alignment.center,
            content=ft.Row([
                ft.Container(width=4,height=7,bgcolor='#75464B',border_radius=4),
                ft.Container(width=4,height=7,bgcolor='#75464B',border_radius=4),
            ],alignment=ft.MainAxisAlignment.CENTER,spacing=6)))

def skin_scan_motif(size=104):
    """A small, abstract skin-scan illustration for image-related empty states."""
    s=float(size)
    dot=max(5,round(s*.065))
    return ft.Stack(width=s,height=s,controls=[
        ft.Container(width=s*.82,height=s*.82,left=s*.02,top=s*.02,
            bgcolor=INNER,border=ft.border.all(1,BORDER),border_radius=s*.41),
        ft.Container(width=s*.60,height=s*.60,left=s*.13,top=s*.13,
            border=ft.border.all(1,BORDER),border_radius=s*.30),
        ft.Container(width=s*.37,height=s*.37,left=s*.245,top=s*.245,
            bgcolor=CHIP_BG,border=ft.border.all(1,'#E6D2D4' if theme_color_light() else '#574047'),
            border_radius=s*.185),
        ft.Container(width=dot,height=dot,left=s*.37,top=s*.35,bgcolor=PINK,border_radius=dot),
        ft.Container(width=dot*.72,height=dot*.72,left=s*.53,top=s*.49,bgcolor=STRAW,border_radius=dot),
        ft.Container(width=s*.20,height=s*.20,left=s*.60,top=s*.60,bgcolor=PANEL,
            border=ft.border.all(1,BORDER),border_radius=s*.10,alignment=ft.alignment.center,
            content=ft.Icon(ft.Icons.SEARCH_ROUNDED,size=s*.14,color=PRIMARY)),
    ])

def theme_color_light():
    return BG==PALETTES['light']['BG']

def apply_palette(name):
    global BG,SIDEBAR,PANEL,INNER,BORDER,PRIMARY,SLATE,GREEN,STRAW,PINK,INK,QUIET,RED
    global BAR_BG,HEADER_BG,CHIP_BG,IMAGE_BG,STATUS_BG,NAV_SELECTED
    palette=PALETTES[name]
    BG=palette['BG']; SIDEBAR=palette['SIDEBAR']; PANEL=palette['PANEL']; INNER=palette['INNER']
    BORDER=palette['BORDER']; PRIMARY=palette['PRIMARY']; SLATE=palette['SLATE']; GREEN=palette['GREEN']
    STRAW=palette['STRAW']; PINK=palette['PINK']; INK=palette['INK']; QUIET=palette['QUIET']; RED=palette['RED']
    BAR_BG=palette['BAR_BG']; HEADER_BG=palette['HEADER_BG']; CHIP_BG=palette['CHIP_BG']
    IMAGE_BG=palette['IMAGE_BG']; STATUS_BG=palette['STATUS_BG']; NAV_SELECTED=palette['NAV_SELECTED']

def main(page:ft.Page):
    page.title='PigSkin AI Studio — Sức khỏe da heo'; page.padding=0;page.spacing=0
    page.bgcolor=BG; page.theme_mode=ft.ThemeMode.LIGHT
    page.window.width=1510;page.window.height=920;page.window.min_width=1000;page.window.min_height=690
    page.theme=ft.Theme(color_scheme_seed=PRIMARY,font_family='Segoe UI',visual_density=ft.VisualDensity.STANDARD)
    selected={'path':None,'info':None,'result':None,'record_id':None}
    page_title=label('Tổng quan',22,INK,True)
    subtitle=label('Theo dõi sức khỏe da heo',12,QUIET)
    screen_switcher=ft.AnimatedSwitcher(
        content=ft.Column(expand=True,scroll=ft.ScrollMode.AUTO,spacing=17),
        duration=170,reverse_duration=120,
        switch_in_curve=ft.AnimationCurve.EASE_OUT,
        switch_out_curve=ft.AnimationCurve.EASE_IN,
        transition=ft.AnimatedSwitcherTransition.FADE,
        expand=True)
    nav=[]
    active_page={'index':0}
    theme_choice={'value':'light'}

    def notify(message,color=None):
        color=PRIMARY if color is None else color
        page.snack_bar=ft.SnackBar(content=label(message,13,INK),bgcolor=PANEL)
        page.snack_bar.open=True;page.update()

    def dashboard():
        rows=recent()
        run=active_run()
        dataset=run.get('data') if run else None
        split_counts=dataset.get('split_counts',{}) if dataset else {}
        total_images=dataset.get('total') if dataset else None
        test_metrics=(run.get('metrics',{}).get('test_metrics',{}) if run else {})
        val_macro_f1=(run.get('metrics',{}).get('best_val_macro_f1') if run else None)
        pending=sum(1 for item in rows if (item.get('review_status') or 'needs_review')=='needs_review')
        inferred_rows=[item for item in rows if item['mode']=='ai' and item.get('predicted_class')]
        inferred=len(inferred_rows)
        class_counts=Counter(item['predicted_class'] for item in inferred_rows)
        header=ft.Container(bgcolor=HEADER_BG,border=ft.border.all(1,BORDER),border_radius=12,padding=17,
            content=ft.Row([pig_mark(46),
                ft.Column([label('Trạm theo dõi sức khỏe đàn heo',21,INK,True),
                    label('Tiếp nhận ảnh da, ghi nhận dấu hiệu và xem lại kết quả nghiên cứu.',12)],spacing=4,expand=True),
                skin_scan_motif(96),
                ft.Container(bgcolor=STATUS_BG,padding=10,border_radius=9,
                    content=label('Có mô hình hỗ trợ' if model_ready() else 'Chưa kết nối mô hình',11,STRAW,True)),
                ft.ElevatedButton('Tiếp nhận ảnh',icon=ft.Icons.ADD_A_PHOTO,
                    on_click=lambda _:navigate(1),bgcolor=PRIMARY,color='#FFFFFF')],spacing=12))
        stats=ft.Row([kpi('Hồ sơ gần đây',str(len(rows)),ft.Icons.FOLDER_OUTLINED,PRIMARY,'Tối đa 300 hồ sơ trong danh sách'),
            kpi('Chờ rà soát',str(pending),ft.Icons.HISTORY,STRAW,'Cần chuyên gia xác minh'),
            kpi('Có kết quả AI',str(inferred),ft.Icons.AUTO_AWESOME,GREEN,'Số hồ sơ chạy được checkpoint'),
            kpi('Ảnh bộ dữ liệu',str(total_images) if total_images is not None else '—',
                ft.Icons.IMAGE_OUTLINED,SLATE,'Đọc từ manifest' if dataset else 'Chưa tìm thấy manifest')],spacing=10)
        queue_lines=[]
        review_labels={'needs_review':'CHỜ RÀ SOÁT','reviewed':'ĐÃ RÀ SOÁT',
                       'lab_requested':'CẦN XÉT NGHIỆM','closed':'ĐÃ ĐÓNG'}
        for item in rows[:6]:
            status=item.get('review_status') or 'needs_review'
            prediction=display_class(item['predicted_class']) if item['predicted_class'] else 'Chưa có dự đoán AI'
            confidence=f" • {item['confidence']*100:.1f}% softmax" if item['confidence'] is not None else ''
            context=' • '.join(value for value in (item.get('farm_name'),item.get('body_site')) if value)
            queue_lines.append(ft.Container(padding=9,border=ft.border.only(bottom=ft.BorderSide(1,BORDER)),
                content=ft.Row([ft.Column([label(f"{item.get('case_id') or 'Hồ sơ cũ'}  /  {item.get('animal_id') or 'Chưa gắn mã cá thể'}",12,PRIMARY,True),
                    label(f"{item['filename']} • {context or 'Chưa có thông tin vị trí/cơ sở'}",10),
                    label(f"{prediction}{confidence}",11,INK)],spacing=3,expand=True),
                    label(review_labels.get(status,'CHỜ RÀ SOÁT'),9,STRAW if status=='needs_review' else GREEN,True)])))
        cases=block([ft.Row([caption_head('Hồ sơ cần theo dõi','Ảnh và nhận định mới nhất',ft.Icons.VIEW_LIST),
                    ft.Container(expand=True),ft.TextButton('MỞ LỊCH SỬ',on_click=lambda _:navigate(2))]),
                    *(queue_lines or [label('Chưa có hồ sơ. Tạo ca đầu tiên từ màn hình Phân tích ảnh.',12)]),
                    ft.TextButton('TIẾP NHẬN ẢNH MỚI',icon=ft.Icons.ADD_A_PHOTO,on_click=lambda _:navigate(1))],expand=3,padding=14)
        system=block([caption_head('Thiết bị nghiên cứu','Các thành phần ứng dụng',ft.Icons.HUB),
            ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE,color=GREEN,size=17),label('Ứng dụng máy tính',11,INK,True)]),
            ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE,color=GREEN,size=17),label('Lưu hồ sơ trên thiết bị',11,INK,True)]),
            ft.Row([ft.Icon(ft.Icons.WARNING_AMBER,color=STRAW,size=17),
                label('Checkpoint và class map' if model_ready() else 'Chưa có trọng số AI',11,STRAW,True)]),
            label('App kiểm tra checkpoint bằng suy luận khi có ảnh.',10),
            ft.Divider(color=BORDER),label(
                f"Phân loại toàn ảnh • {run['config'].get('model','').replace('_',' ').title()}" if run else 'Chưa nạp kiến trúc mô hình',10,INK),
            label('Chưa có detection box hoặc heatmap.',10)],expand=2,padding=14)
        if dataset and total_images:
            split_content=[
                meter(f"Tập huấn luyện • {split_counts.get('train',0)} ảnh",split_counts.get('train',0)/total_images,SLATE),
                meter(f"Xác thực • {split_counts.get('val',0)} ảnh",split_counts.get('val',0)/total_images,STRAW),
                meter(f"Kiểm tra • {split_counts.get('test',0)} ảnh",split_counts.get('test',0)/total_images,GREEN),
                label(f"Đọc manifest: {dataset['path']}",9),
            ]
            if not dataset.get('matches_run',True):
                split_content.append(label('Cảnh báo: manifest hiện tại khác hash đã ghi trong lần train này.',10,RED))
        else:
            split_content=[label('Không tìm thấy manifest thật; số lượng không được ước đoán.',12,STRAW)]
        split=block([caption_head('Dữ liệu huấn luyện','Số lượng lấy trực tiếp từ manifest',ft.Icons.DONUT_LARGE),
            *split_content],expand=1,padding=14)
        if run and val_macro_f1 is not None and test_metrics:
            evaluation_content=[
                meter('Macro-F1 xác thực tốt nhất',float(val_macro_f1),SLATE),
                meter('Macro-F1 tập kiểm tra',float(test_metrics.get('macro_f1',0)),GREEN),
                meter('Độ chính xác tập kiểm tra',float(test_metrics.get('accuracy',0)),STRAW),
                label(f"Lần train {run['name']} • số liệu từ final_metrics.json",10),
            ]
        else:
            evaluation_content=[label('Chưa có final_metrics.json hợp lệ cho lần train.',12,STRAW)]
        evaluation=block([caption_head('Kết quả mô hình','Đọc từ báo cáo của checkpoint đã chọn',ft.Icons.ANALYTICS),
            *evaluation_content],expand=1,padding=14)
        if class_counts:
            ranked=class_counts.most_common()
            chart_width=max(420,min(900,page.window.width-510))
            chart=ft.LineChart(
                data_series=[ft.LineChartData(
                    color=PRIMARY,curved=True,stroke_width=3,stroke_cap_round=True,point=True,
                    below_line_bgcolor=ft.Colors.with_opacity(0.18,PRIMARY),
                    data_points=[ft.LineChartDataPoint(
                        index,count/inferred*100,show_tooltip=True,
                        tooltip=f'{display_class(name)}: {count} hồ sơ ({count/inferred*100:.1f}%)')
                        for index,(name,count) in enumerate(ranked)],
                )],
                min_x=0,max_x=max(len(ranked)-1,1),min_y=0,max_y=100,
                width=chart_width,height=270,interactive=True,animate=220,
                left_axis=ft.ChartAxis(labels=[ft.ChartAxisLabel(value=value,
                    label=label(f'{value}%',9,QUIET)) for value in (0,25,50,75,100)],labels_size=34),
                bottom_axis=ft.ChartAxis(labels=[ft.ChartAxisLabel(value=index,label=label(
                    display_class(name) if len(display_class(name))<=10 else display_class(name)[:9]+'..',9,QUIET))
                    for index,(name,_) in enumerate(ranked)],labels_size=42),
                horizontal_grid_lines=ft.ChartGridLines(interval=25,color=BORDER,width=1),
                tooltip_bgcolor=SIDEBAR)
            distribution_content=ft.Column([chart,label(
                f'Top-1 trên {inferred} hồ sơ AI trong tối đa 300 hồ sơ mới nhất; không phải tỷ lệ mắc bệnh.',10,STRAW)],spacing=4)
        else:
            distribution_content=ft.Container(height=270,alignment=ft.alignment.center,
                content=ft.Column([ft.Icon(ft.Icons.BAR_CHART,size=42,color=QUIET),
                    label('Chưa có hồ sơ chạy AI để lập biểu đồ.',12,INK,True),
                    label('Cần checkpoint tương thích và class map thật.',10)],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,alignment=ft.MainAxisAlignment.CENTER,spacing=7))
        distribution=block([caption_head('Phân bố nhãn AI','Tần suất lớp đứng đầu trên các hồ sơ đã phân tích',ft.Icons.BAR_CHART),
            distribution_content],expand=1,padding=14)
        return [header,stats,ft.Row([distribution],spacing=10),
                ft.Row([cases,system],spacing=10,vertical_alignment=ft.CrossAxisAlignment.START),
                ft.Row([split,evaluation],spacing=10,vertical_alignment=ft.CrossAxisAlignment.START)]

    # Single picker registered once; reusable across visits.
    image=ft.Image(width=480,height=340,fit=ft.ImageFit.CONTAIN,visible=False)
    noimage=ft.Column([skin_scan_motif(112),
        label('Chọn ảnh da heo',18,INK,True),label('JPG / PNG / WEBP • Tối đa 10 MB',12)],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,alignment=ft.MainAxisAlignment.CENTER,spacing=10)
    preview_switcher=ft.AnimatedSwitcher(content=noimage,
        transition=ft.AnimatedSwitcherTransition.FADE,duration=210,reverse_duration=140,
        switch_in_curve=ft.AnimationCurve.EASE_OUT,expand=True)
    preview_frame=ft.Container(content=preview_switcher,bgcolor=INNER,height=366,alignment=ft.alignment.center,
                               border=ft.border.all(1,BORDER),border_radius=12)
    file_line=label('Chưa chọn ảnh',12)
    notice=label('AI chưa sẵn sàng. Bạn có thể kiểm tra ảnh và lưu lịch sử.',12,STRAW)
    result_switcher=ft.AnimatedSwitcher(
        content=ft.Column([skin_scan_motif(96),
            label('Chờ phân tích',19,INK,True),label('Chọn ảnh rồi nhấn “Kiểm tra ảnh”.')],spacing=13),
        transition=ft.AnimatedSwitcherTransition.FADE,duration=190,reverse_duration=130,
        switch_in_curve=ft.AnimationCurve.EASE_OUT,expand=True)
    analysis_progress=ft.ProgressBar(value=None,color=PRIMARY,bgcolor=BAR_BG,visible=False)
    analysis_busy={'value':False}
    analysis_button=None
    choose_button=None
    clear_button=None
    case_identifier=label('CHƯA TẠO HỒ SƠ',13,INK,True)
    case_state=label('CHỜ TIẾP NHẬN',11,STRAW,True)
    received_at_label=label('Chưa ghi nhận',11,INK,True)
    entered_at={'value':''}
    entered_at_label=label('Thời điểm nhập sẽ hiện tại đây',10,GREEN)
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
        if not r:
            controls=[skin_scan_motif(96),
                label('Chờ phân tích',19,INK,True),label('Chọn ảnh rồi nhấn “Kiểm tra ảnh”.')]
        elif r['mode']!='ai':
            controls=[ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE,size=58,color=GREEN),
                label('Ảnh đã kiểm tra',20,INK,True),label(r['message'],13,STRAW)]
        else:
            controls=[ft.Icon(ft.Icons.AUTO_AWESOME,size=48,color=GREEN),
              label('Gợi ý từ mô hình • cần chuyên gia rà soát',11,GREEN,True),
              label(r.get('display_label',display_class(r['label'])),21,INK,True),
              label(f"Điểm softmax (chưa hiệu chuẩn): {r['confidence']*100:.1f}%",12,STRAW),
              label('Các lớp có điểm cao nhất; đây không phải xác suất chẩn đoán:',11),
              *[meter(display_class(s['label']),s['confidence'],PRIMARY) for s in r['scores']]]
        if selected['record_id']:
            controls.append(label(f"Mã hồ sơ: PS-{selected['record_id']:06d} • Cần chuyên gia xác minh",11,STRAW))
        if r and r.get('model_info'):
            controls.append(label(f"Mô hình: {r['model_info']}",10))
        result_switcher.content=ft.Column(controls,spacing=13)

    def selected_file(e):
        if not e.files: return
        path=e.files[0].path
        try:
            info=inspect_image(path)
            if selected['record_id']:
                reset_case_context()
            selected.update(path=path,info=info,result=None,record_id=None)
            image.src_base64=base64.b64encode(Path(path).read_bytes()).decode('ascii')
            image.visible=True;preview_switcher.content=image
            case_identifier.value='HỒ SƠ SẼ ĐƯỢC TẠO KHI KIỂM TRA'
            case_state.value='ẢNH ĐÃ NẠP • CHỜ PHÂN TÍCH'
            file_line.value=f"{info['name']} • {info['width']}×{info['height']} px • {info['bytes']/1048576:.2f} MB"
            notice.value='Ảnh hợp lệ, có thể bắt đầu kiểm tra.';notice.color=GREEN
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

    async def process_image(e):
        if not selected['path']:
            notify('Bạn chưa chọn ảnh.');return
        if selected['record_id']:
            notify('Hồ sơ này đã được lưu. Chọn “Ca mới” để tiếp nhận ảnh khác.');return
        if analysis_busy['value']:
            return
        source_path=selected['path']
        analysis_busy['value']=True
        analysis_progress.visible=True
        if analysis_button: analysis_button.disabled=True
        if choose_button: choose_button.disabled=True
        if clear_button: clear_button.disabled=True
        notice.value='Đang chạy mô hình trên ảnh…';notice.color=SLATE
        page.update()
        try:
            info=inspect_image(source_path)
            result=await asyncio.to_thread(predict,source_path)
            if selected['path']!=source_path:
                return
            case={'animal_id':animal_id_field.value or '', 'farm_name':farm_field.value or '',
                'body_site':body_site_field.value or '', 'onset_date':onset_field.value or '',
                'symptoms':symptoms_field.value or '', 'entered_at':entered_at['value']}
            rid=save(info,result,case,selected['path'])
            selected.update(info=info,result=result,record_id=rid)
            saved_record=next((item for item in recent() if item['id']==rid),None)
            case_identifier.value=f'PS-{rid:06d}'
            case_state.value='ĐÃ LƯU • CHỜ CHUYÊN GIA RÀ SOÁT'
            received_at_label.value=saved_record['created_at'] if saved_record else 'Đã lưu thời gian tiếp nhận'
            notice.value=f'Đã lưu hồ sơ PS-{rid:06d} vào SQLite.'; notice.color=GREEN
            render_result();page.update()
        except Exception as exc:
            notice.value=f'Lỗi: {exc}';notice.color=RED;page.update()
        finally:
            analysis_busy['value']=False
            analysis_progress.visible=False
            if analysis_button: analysis_button.disabled=False
            if choose_button: choose_button.disabled=False
            if clear_button: clear_button.disabled=False
            page.update()

    def clear_image(e):
        saved_record_id=selected['record_id']
        selected.update(path=None,info=None,result=None)
        preview_switcher.content=noimage;image.visible=False;image.src_base64=None
        file_line.value='Chưa chọn ảnh'
        if saved_record_id:
            notice.value=f'Ảnh đã gỡ khỏi phiên xem; hồ sơ PS-{saved_record_id:06d} vẫn được lưu.'
            notice.color=STRAW
        else:
            case_identifier.value='CHƯA TẠO HỒ SƠ'
            case_state.value='CHỜ TIẾP NHẬN'
            received_at_label.value='Chưa ghi nhận'
            notice.value='Chưa chọn ảnh';notice.color=STRAW
        render_result();page.update()

    def start_new_case(e=None):
        selected.update(path=None,info=None,result=None,record_id=None)
        reset_case_context()
        preview_switcher.content=noimage;image.visible=False;image.src_base64=None
        file_line.value='Chưa chọn ảnh'
        notice.value='Ca mới chưa có ảnh.';notice.color=STRAW
        render_result();page.update()

    def analysis():
        nonlocal analysis_button,choose_button,clear_button
        render_result()
        case_header=ft.Container(bgcolor=HEADER_BG,border=ft.border.all(1,BORDER),border_radius=12,padding=14,
            content=ft.Row([ft.Icon(ft.Icons.FOLDER_SHARED_OUTLINED,color=PRIMARY,size=22),
                ft.Column([label('Hồ sơ tiếp nhận',11,PRIMARY,True),case_identifier],spacing=3,expand=True),
                ft.Container(width=1,height=34,bgcolor=BORDER),
                ft.Column([label('Trạng thái',10,QUIET,True),case_state],spacing=3),
                ft.Container(width=1,height=34,bgcolor=BORDER),
                ft.Column([label('Thời điểm tiếp nhận',10,QUIET,True),received_at_label],spacing=3),
                ft.Container(width=1,height=34,bgcolor=BORDER),
                ft.Column([label('Nguồn ảnh',10,QUIET,True),label('Ảnh màu RGB',11,INK,True)],spacing=3)],spacing=15))
        image_panel=block([caption_head('Ảnh tổn thương','Đưa vùng da cần kiểm tra vào khung hình',ft.Icons.IMAGE_SEARCH),
            ft.Container(content=preview_frame,bgcolor=IMAGE_BG,padding=8,border_radius=10),file_line,
            label('Ảnh nguồn được sao chép vào kho hồ sơ cục bộ khi lưu.',10),
            analysis_progress,
            ft.Row([choose_button:=ft.ElevatedButton('Chọn ảnh',icon=ft.Icons.FOLDER_OPEN,on_click=choose_image,bgcolor=PRIMARY,color='#FFFFFF'),
                clear_button:=ft.OutlinedButton('Xóa ảnh',icon=ft.Icons.DELETE_OUTLINE,on_click=clear_image),
                analysis_button:=ft.ElevatedButton('Kiểm tra ảnh',icon=ft.Icons.PLAY_ARROW,on_click=process_image,bgcolor=SLATE,color='#FFFFFF')],wrap=True),
            notice],expand=3)
        result_panel=block([ft.Row([caption_head('Nhận định từ mô hình','Kết quả hỗ trợ nghiên cứu',ft.Icons.BIOTECH),
                    ft.Container(expand=True),ft.Container(bgcolor=CHIP_BG,padding=8,border_radius=6,
                        content=label('Phân loại ảnh',10,PINK,True))]),
                    ft.Container(content=result_switcher,bgcolor=INNER,padding=18,border_radius=8,height=430,
                        alignment=ft.alignment.top_left),
                    ft.Divider(color=BORDER,height=1),
                    ft.Row([ft.Icon(ft.Icons.MEMORY,color=SLATE,size=17),
                        label('MobileNetV2 • 10 lớp • input 224×224',11,INK,True)]),
                    label('Checkpoint: '+('đã phát hiện file' if model_ready() else 'chưa tích hợp'),11,STRAW),
                    label('Đây là phân loại toàn ảnh; hiện chưa có bounding box/segmentation.',10),
                    label('Softmax chưa hiệu chuẩn, không phải xác suất bệnh. Cần chuyên gia xác minh.',10,STRAW)],expand=2)
        clinical_context=block([ft.Row([caption_head('Thông tin quan sát','Ghi nhận tại thời điểm tiếp nhận, chưa phải kết luận bệnh',ft.Icons.ASSIGNMENT_OUTLINED),
                ft.Container(expand=True),label('Lưu cùng hồ sơ',10,GREEN,True),
                ft.OutlinedButton('Ca mới',icon=ft.Icons.ADD,on_click=start_new_case)]),
            ft.Row([animal_id_field,farm_field],spacing=10),
            ft.Row([body_site_field,onset_field],spacing=10),
            ft.Row([ft.Column([symptoms_field,entered_at_label],spacing=4,expand=True),
                    ft.Column([label('NGÀY KHỞI PHÁT',9,QUIET,True),
                        label('Nhập tay nếu biết; thời điểm nhập được ghi riêng.',10)],spacing=4)]),
            ],padding=14)
        return [case_header,ft.Row([image_panel,result_panel],spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.START),clinical_context]

    def history_view():
        term=ft.TextField(hint_text='Tìm mã ca, mã heo, cơ sở hoặc tên ảnh...',
                          prefix_icon=ft.Icons.SEARCH,expand=True,dense=True)
        rows_area=ft.Column(spacing=0)
        count=label('',13,PRIMARY,True)
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
                    label(f"{it['case_id'] or 'Hồ sơ cũ'} • {it['animal_id'] or 'Chưa gắn mã cá thể'}",12,PRIMARY,True),
                    label(f"{it['filename']} • Tiếp nhận: {it['created_at']}",10),
                    label(f"{context or 'Chưa có thông tin cơ sở/vị trí'}",10),
                    label(f"Mô tả: {symptoms}",10,INK),
                    label(f"{prediction}{score_text} • {len(scores)} lớp đã lưu",11,INK)],spacing=3,expand=True),
                    ft.IconButton(icon=ft.Icons.IMAGE_SEARCH,icon_color=GREEN,tooltip='Xem ảnh gốc',
                        disabled=not bool(it.get('image_path')),
                        on_click=lambda e,record=it:show_image(record)),
                    ft.IconButton(icon=ft.Icons.EDIT_OUTLINED,icon_color=SLATE,tooltip='Sửa hồ sơ',
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
            dialog=ft.AlertDialog(modal=True,title=label(f"Ảnh hồ sơ • {record['filename']}",16,INK,True),
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
            dialog=ft.AlertDialog(modal=True,title=label(f"Sửa hồ sơ {record.get('case_id') or record['id']}",17,INK,True),
                content=ft.Container(width=520,content=ft.Column([
                    animal,farm,site,onset,symptoms,
                    label(f"Tiếp nhận lúc: {record['created_at']}",10,QUIET)],spacing=9,tight=True,
                    scroll=ft.ScrollMode.AUTO)),
                actions=[ft.TextButton('Hủy',on_click=lambda e:page.close(dialog)),
                    ft.ElevatedButton('LƯU THAY ĐỔI',icon=ft.Icons.SAVE,on_click=save_changes,
                        bgcolor=PRIMARY,color=BG)],actions_alignment=ft.MainAxisAlignment.END,bgcolor=PANEL)
            page.open(dialog)
        term.on_change=load
        review_filter.on_change=load
        load()
        return [block([caption_head('Lịch sử kiểm tra ảnh','Ảnh gốc được lưu cục bộ cùng hồ sơ',ft.Icons.HISTORY),
                ft.Row([term,review_filter,ft.OutlinedButton('Làm mới',icon=ft.Icons.REFRESH,on_click=load)]),
                ft.Row([label('HỒ SƠ / QUAN SÁT / NHẬN ĐỊNH',10,PRIMARY,True),ft.Container(expand=True),
                    label('SỬA',10,SLATE,True),label('TRẠNG THÁI',10,PRIMARY,True),label('XÓA',10,RED,True)],spacing=12),count,
                ft.Container(content=rows_area,bgcolor=INNER,border_radius=10,padding=8)],padding=20)]

    def dataset():
        run=active_run()
        data=run.get('data') if run else None
        config=run.get('config',{}) if run else {}
        counts=data.get('split_counts',{}) if data else {}
        total=data.get('total') if data else 0
        summary=ft.Row([
            kpi('Tổng số ảnh',str(total) if data else '—',ft.Icons.IMAGE,SLATE,'Đọc từ manifest'),
            kpi('Tập huấn luyện',str(counts.get('train','—')),ft.Icons.SCHOOL,SLATE,'train'),
            kpi('Tập xác thực',str(counts.get('val','—')),ft.Icons.VERIFIED,STRAW,'validation'),
            kpi('Tập kiểm tra',str(counts.get('test','—')),ft.Icons.FACT_CHECK,GREEN,'test'),
        ],spacing=10)
        if data and total:
            split_content=[
                meter('Huấn luyện',counts.get('train',0)/total,SLATE,f"{counts.get('train',0):,} ảnh"),
                meter('Xác thực',counts.get('val',0)/total,STRAW,f"{counts.get('val',0):,} ảnh"),
                meter('Kiểm tra',counts.get('test',0)/total,GREEN,f"{counts.get('test',0):,} ảnh"),
            ]
            class_counts=data['class_counts']
            classes=config.get('classes',[])
            class_rows=[ft.Container(padding=8,border=ft.border.only(bottom=ft.BorderSide(1,BORDER)),
                content=ft.Row([
                    label(display_class(name),11,INK,True,expand=True),
                    label(str(class_counts['train'].get(name,0)),11,SLATE),
                    label(str(class_counts['val'].get(name,0)),11,STRAW),
                    label(str(class_counts['test'].get(name,0)),11,GREEN),
                ],spacing=15)) for name in classes]
            table=block([
                caption_head('Số ảnh theo nhãn','Đếm trực tiếp từng dòng trong manifest',ft.Icons.VIEW_LIST),
                ft.Row([label('Lớp',10,QUIET,True,expand=True),label('Train',10,SLATE,True),
                    label('Val',10,STRAW,True),label('Test',10,GREEN,True)],spacing=15),
                *(class_rows or [label('Manifest chưa có nhãn lớp.',11,STRAW)]),
            ],padding=12)
            hash_ok=data.get('matches_run',True)
            audit_state='Khớp hash manifest đã lưu cùng lần train' if hash_ok else 'Hash manifest khác với lần train'
            audit_color=GREEN if hash_ok else RED
            split_content.extend([
                label(f"Nguồn thật: {data['path']}",9),
                label(f"SHA-256: {data['sha256']}",9),
            ])
        else:
            split_content=[label('Không tìm thấy manifest thật; không hiển thị số liệu thay thế.',12,STRAW)]
            table=block([caption_head('Số ảnh theo nhãn','Chưa có manifest để thống kê',ft.Icons.VIEW_LIST),
                label('Chọn đúng thư mục training studio hoặc đặt biến PIGSKIN_RESEARCH_ROOT.',11)])
            audit_state='Chưa đọc được manifest'
            audit_color=STRAW
        split=block([caption_head('Phân chia dữ liệu','Tỷ lệ được tính từ manifest hiện có',ft.Icons.DONUT_LARGE),
            *split_content],expand=1,padding=14)
        audit=block([caption_head('Kiểm tra nguồn dữ liệu','Thông tin lần train đang dùng',ft.Icons.FACT_CHECK),
            ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE if data else ft.Icons.WARNING_AMBER,color=audit_color,size=17),
                label(audit_state,11,audit_color,True)]),
            label(f"Lần train: {run['name']}" if run else 'Chưa tìm thấy lần train hoàn chỉnh',11,INK),
            label(f"Model: {config.get('model','—')} • input {config.get('image_size','—')} px",11),
            label(f"Số lớp: {len(config.get('classes',[]))}",11),
            label('Thống kê nguồn này không bao gồm các ảnh đã thêm thủ công trong lịch sử kiểm tra.',10)],
            expand=1,padding=14)
        return [ft.Row([ft.Column([label('Dữ liệu nghiên cứu',23,INK,True),
                    label(f"Manifest • run {run['name']}" if run else 'Chưa tìm thấy manifest hoặc run',11)],spacing=4),
                ft.Container(expand=True),label('SỐ LIỆU ĐỌC TỪ FILE',10,PRIMARY,True)]),
            summary,ft.Row([split,audit],spacing=10,vertical_alignment=ft.CrossAxisAlignment.START),table]

    def training():
        run=active_run()
        config=run.get('config',{}) if run else {}
        report=run.get('metrics',{}) if run else {}
        test=report.get('test_metrics',{})
        best_val=report.get('best_val_macro_f1')
        best_epoch=report.get('best_epoch')
        metric_text=lambda value: f"{float(value):.4f}" if value is not None else '—'
        metrics=ft.Row([
            kpi('Epoch tốt nhất',str(best_epoch) if best_epoch is not None else '—',ft.Icons.TIMELINE,SLATE,run['name'] if run else 'Chưa có run'),
            kpi('Macro-F1 xác thực',metric_text(best_val),ft.Icons.ANALYTICS,GREEN,'best validation'),
            kpi('Macro-F1 kiểm tra',metric_text(test.get('macro_f1')),ft.Icons.INSERT_CHART,SLATE,'test set'),
            kpi('Độ chính xác kiểm tra',f"{float(test['accuracy'])*100:.2f}%" if test.get('accuracy') is not None else '—',
                ft.Icons.TRACK_CHANGES,STRAW,'test set'),
        ],spacing=10)
        if run and test:
            performance_items=[
                meter('Macro-F1 xác thực tốt nhất',float(best_val or 0),SLATE),
                meter('Macro-F1 tập kiểm tra',float(test.get('macro_f1',0)),GREEN),
                meter('Độ chính xác tập kiểm tra',float(test.get('accuracy',0)),STRAW),
                meter('Macro-precision kiểm tra',float(test.get('macro_precision',0)),SLATE),
                meter('Macro-recall kiểm tra',float(test.get('macro_recall',0)),GREEN),
                label(f"Loss kiểm tra: {float(test.get('loss',0)):.4f}",11),
            ]
            per_class=test.get('per_class',{})
            class_performance=[ft.Container(padding=8,border=ft.border.only(bottom=ft.BorderSide(1,BORDER)),
                content=ft.Row([label(display_class(name),11,INK,True,expand=True),
                    ft.ProgressBar(value=float(values.get('f1',0)),width=150,
                        color=PRIMARY,bgcolor=BAR_BG,bar_height=8),
                    label(f"{float(values.get('f1',0)):.3f}",10,PRIMARY,True)],spacing=10))
                for name,values in per_class.items()]
        else:
            performance_items=[label('Không tìm thấy final_metrics.json; chưa có số liệu để trình bày.',12,STRAW)]
            class_performance=[]
        performance=block([caption_head('Chỉ số trên tập test','Đọc từ final_metrics.json của run',ft.Icons.ANALYTICS),
            *performance_items],expand=1,padding=14)
        optimizer=config.get('optimizer','—')
        loss_name=config.get('loss','—')
        reproducibility=block([caption_head('Cấu hình và nguồn kết quả','Đọc từ config.json và final_metrics.json',ft.Icons.SCIENCE_OUTLINED),
            ft.Row([label('Mã lần chạy',11),ft.Container(expand=True),label(run['name'] if run else '—',11,INK,True)]),
            ft.Row([label('Kiến trúc',11),ft.Container(expand=True),label(config.get('model','—'),11,INK,True)]),
            ft.Row([label('Optimizer / loss',11),ft.Container(expand=True),label(f'{optimizer} / {loss_name}',11,INK,True)]),
            ft.Row([label('Batch / kích thước ảnh',11),ft.Container(expand=True),label(
                f"{config.get('batch_size','—')} / {config.get('image_size','—')} px",11,INK,True)]),
            ft.Row([label('Learning rate',11),ft.Container(expand=True),label(
                f"head {config.get('head_lr','—')} • fine-tune {config.get('finetune_lr','—')}",10,INK,True)]),
            ft.Row([label('Epoch tốt nhất',11),ft.Container(expand=True),label(str(best_epoch or '—'),11,INK,True)]),
            ft.Divider(color=BORDER),
            label(f"Checkpoint: {run['checkpoint']}" if run else 'Chưa có checkpoint',10),
            label('Điểm số là kết quả đánh giá trên tập test đã lưu, không phải dự đoán của hồ sơ đang mở.',10,STRAW)],
            expand=1,padding=14)
        class_block=block([caption_head('F1 theo từng lớp','Nhìn lớp mô hình còn nhầm nhiều',ft.Icons.VIEW_LIST),
            *(class_performance or [label('Chưa có chỉ số từng lớp.',11,STRAW)])],padding=14)
        return [ft.Row([ft.Column([label('Kết quả huấn luyện',23,INK,True),
                    label(f"Run {run['name']} • số liệu đọc từ file" if run else 'Chưa có kết quả huấn luyện',11)],spacing=4),
                ft.Container(expand=True),label('Nguồn: artifacts của trainer',10,PRIMARY,True)]),
            metrics,ft.Row([performance,reproducibility],spacing=10,vertical_alignment=ft.CrossAxisAlignment.START),
            class_block]

    def model():
        status=model_status()
        run=status.get('run')
        config=run.get('config',{}) if run else {}
        def dependency_row(name,path,available):
            color=GREEN if available else STRAW
            icon=ft.Icons.CHECK_CIRCLE if available else ft.Icons.WARNING_AMBER
            state='ĐÃ PHÁT HIỆN' if available else 'CHƯA CÓ'
            return ft.Container(padding=9,border=ft.border.only(bottom=ft.BorderSide(1,BORDER)),
                content=ft.Row([ft.Icon(icon,color=color,size=17),
                    ft.Column([label(name,11,INK,True),label(path,9,max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS)],spacing=2,expand=True),
                    label(state,9,color,True)],spacing=10))
        checkpoint_exists=bool(run and run['checkpoint'].is_file())
        classes_exists=bool(config.get('classes'))
        runtime_ready=status.get('runtime_ready',False)
        manifest_ready=bool(run and run.get('data'))
        dependencies=block([caption_head('Kiểm tra thành phần','Có file chưa đồng nghĩa mô hình tương thích',ft.Icons.FACT_CHECK),
            dependency_row('Checkpoint đã train',str(run['checkpoint']) if run else 'Không tìm thấy run',checkpoint_exists),
            dependency_row('Danh sách lớp',str(run['config_path']) if run else 'Không có config.json',classes_exists),
            dependency_row('Python có PyTorch',str(status['python']) if status.get('python') else 'Không tìm thấy môi trường train',runtime_ready),
            dependency_row('Manifest dữ liệu',str(run['data']['path']) if manifest_ready else 'Không đọc được manifest',manifest_ready),
            ft.Container(bgcolor=STATUS_BG,padding=10,border_radius=6,content=label(
                'App dùng chính checkpoint best_model.pt và bộ tiền xử lý được lưu trong run.',10,STRAW))],
            expand=1,padding=14)
        mean=config.get('normalization',{}).get('mean',[.485,.456,.406])
        std=config.get('normalization',{}).get('std',[.229,.224,.225])
        model_name=config.get('model','—')
        specification=block([caption_head('Cấu hình checkpoint','Đọc từ lần huấn luyện đang được chọn',ft.Icons.MEMORY),
            ft.Row([label('Lần train',11),ft.Container(expand=True),label(run['name'] if run else '—',11,INK,True)]),
            ft.Row([label('Kiến trúc',11),ft.Container(expand=True),label(model_name,11,INK,True)]),
            ft.Row([label('Số lớp phân loại',11),ft.Container(expand=True),label(str(len(config.get('classes',[]))),11,INK,True)]),
            ft.Row([label('Kích thước ảnh vào',11),ft.Container(expand=True),label(f"{config.get('image_size','—')} × {config.get('image_size','—')} RGB",11,INK,True)]),
            ft.Row([label('Chuẩn hóa RGB',11),ft.Container(expand=True),label(
                f"mean={mean} • std={std}",9,INK,True)]),
            ft.Row([label('Thiết bị suy luận',11),ft.Container(expand=True),label(
                'CUDA nếu khả dụng, nếu không CPU',10,INK,True)]),
            ft.Divider(color=BORDER),
            label('Checkpoint được nạp với kiến trúc và thứ tự lớp ghi trong chính lần train.',10),
            label('Chỉ phục vụ nghiên cứu, không thay thế đánh giá của bác sĩ thú y.',10)],expand=1,padding=14)
        overall='SẴN SÀNG THỬ SUY LUẬN' if checkpoint_exists and classes_exists and runtime_ready else 'CHƯA ĐỦ THÀNH PHẦN'
        return [ft.Row([ft.Column([label('Mô hình AI',23,INK,True),
                    label('Trạng thái file và môi trường • chưa thay thế kiểm định mô hình',11)],spacing=4),
                ft.Container(expand=True),ft.Container(bgcolor=STATUS_BG,padding=9,border_radius=6,
                    content=label(overall,10,STRAW,True))]),
            ft.Row([dependencies,specification],spacing=10,vertical_alignment=ft.CrossAxisAlignment.START)]

    sections=[dashboard,analysis,history_view,dataset,training,model]
    def navigate(index):
        active_page['index']=index
        page_title.value=PAGES[index][0]
        page_title.color=INK
        subtitle.value=['Tổng quan hoạt động','Kiểm tra ảnh da heo','Hồ sơ đã tiếp nhận',
               'Dữ liệu nghiên cứu','Kết quả huấn luyện','Trạng thái mô hình'][index]
        subtitle.color=QUIET
        screen_switcher.content=ft.Column(controls=sections[index](),expand=True,
            scroll=ft.ScrollMode.AUTO,spacing=16)
        for n,b in enumerate(nav):
            b.bgcolor=NAV_SELECTED if n==index else SIDEBAR
            b.content.controls[0].color=PRIMARY if n==index else QUIET
            b.content.controls[1].color=INK if n==index else QUIET
        page.update()
    def toggle_theme(e):
        theme_choice['value']='light' if theme_choice['value']=='dark' else 'dark'
        render_shell(active_page['index'])
    def render_shell(index):
        apply_palette(theme_choice['value'])
        page.bgcolor=BG
        page.theme_mode=ft.ThemeMode.LIGHT if theme_choice['value']=='light' else ft.ThemeMode.DARK
        page.theme=ft.Theme(color_scheme_seed=PRIMARY,font_family='Segoe UI',visual_density=ft.VisualDensity.STANDARD)
        page_title.color=INK;subtitle.color=PRIMARY
        file_line.color=QUIET;case_identifier.color=INK;case_state.color=STRAW
        received_at_label.color=INK;entered_at_label.color=GREEN
        noimage.controls[0]=skin_scan_motif(112)
        noimage.controls[1].color=INK;noimage.controls[2].color=QUIET
        if not selected['result']:
            render_result()
        preview_frame.bgcolor=INNER;preview_frame.border=ft.border.all(1,BORDER)
        if notice.value.startswith(('Ảnh hợp lệ','Đã lưu hồ sơ')):
            notice.color=GREEN
        elif notice.value.startswith('Lỗi:'):
            notice.color=RED
        else:
            notice.color=STRAW
        nav.clear()
        for idx,(name,icon) in enumerate(PAGES):
            nav.append(ft.Container(ink=True,bgcolor=NAV_SELECTED if idx==index else SIDEBAR,
                padding=ft.padding.symmetric(horizontal=12,vertical=11),border_radius=7,
                animate=ft.Animation(150,ft.AnimationCurve.EASE_OUT),
                on_click=lambda e,i=idx:navigate(i),content=ft.Row([ft.Icon(icon,size=18,color=PRIMARY if idx==index else QUIET),
                    label(name,13,INK if idx==index else QUIET,idx==index)],spacing=11)))
        sidebar=ft.Container(width=228,bgcolor=SIDEBAR,padding=16,
            content=ft.Column([
            ft.Row([pig_mark(42),
                ft.Column([label('PigSkin AI',18,INK,True),label('Nghiên cứu da heo',11,QUIET)],spacing=2)]),
            ft.Container(height=20),label('Không gian làm việc',11,QUIET,True),
            ft.Column(nav,spacing=4),ft.Container(expand=True),
            ft.Column([
                ft.Divider(color=BORDER,height=1),
                label('Trạng thái hệ thống',12,INK,True),
                ft.Row([ft.Container(width=7,height=7,bgcolor=GREEN if model_ready() else STRAW,border_radius=4),
                    label('Mô hình đã sẵn sàng' if model_ready() else 'Đang chờ checkpoint',11,GREEN if model_ready() else STRAW)]),
                ft.Row([ft.Container(width=7,height=7,bgcolor=GREEN,border_radius=4),label('Lưu trữ hồ sơ cục bộ',11,QUIET)]),
                ft.Container(height=5),label('Công cụ nghiên cứu • 2026',10,QUIET)],spacing=8)],expand=True))
        theme_button=ft.IconButton(icon=ft.Icons.LIGHT_MODE if theme_choice['value']=='dark' else ft.Icons.DARK_MODE,
            tooltip='Chuyển sang giao diện sáng' if theme_choice['value']=='dark' else 'Chuyển sang giao diện tối',
            on_click=toggle_theme)
        header=ft.Container(bgcolor=PANEL,height=58,
            padding=ft.padding.symmetric(horizontal=24,vertical=8),
            border=ft.border.only(bottom=ft.BorderSide(1,BORDER)),content=ft.Row([
                ft.Column([page_title,subtitle],spacing=1),ft.Container(expand=True),
                ft.Container(bgcolor=INNER,border_radius=6,padding=ft.padding.symmetric(horizontal=10,vertical=7),
                    content=ft.Row([ft.Container(width=7,height=7,bgcolor=GREEN if model_ready() else STRAW,border_radius=4),
                        label('Checkpoint sẵn sàng' if model_ready() else 'Chưa có checkpoint',11,INK)] ,spacing=7)),
                theme_button],spacing=12))
        workspace=ft.Container(expand=True,bgcolor=PANEL,border=ft.border.all(1,BORDER),border_radius=16,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,content=ft.Column([
                header,ft.Container(content=screen_switcher,padding=24,expand=True)],expand=True,spacing=0))
        page.controls.clear()
        page.add(ft.Container(expand=True,bgcolor=BG,padding=8,
            content=ft.Row([sidebar,workspace],spacing=8,expand=True,vertical_alignment=ft.CrossAxisAlignment.STRETCH)))
        navigate(index)
    render_shell(0)

if __name__=='__main__':
    ft.app(target=main)
