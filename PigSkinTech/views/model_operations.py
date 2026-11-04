"""Model Operations page for the existing Flet desktop shell."""

import json

import flet as ft

from services.inference import CLASSES, MODEL_MANIFEST, WEIGHTS, labels, model_spec, model_status


def build_model_view(palette, label, block, caption_head):
    CYAN = palette['CYAN']
    TEAL = palette['TEAL']
    AMBER = palette['AMBER']
    WHITE = palette['WHITE']
    BORDER = palette['BORDER']
    STATUS_BG = palette['STATUS_BG']

    def dependency_row(name, path, available):
        color = TEAL if available else AMBER
        icon = ft.Icons.CHECK_CIRCLE if available else ft.Icons.WARNING_AMBER
        state = 'ĐÃ PHÁT HIỆN' if available else 'CHƯA CÓ'
        return ft.Container(padding=9, border=ft.border.only(bottom=ft.BorderSide(1, BORDER)),
            content=ft.Row([ft.Icon(icon, color=color, size=17),
                ft.Column([label(name, 11, WHITE, True), label(path, 10)], spacing=2, expand=True),
                label(state, 9, color, True)], spacing=10))

    checkpoint_exists = WEIGHTS.is_file()
    classes_exists = CLASSES.is_file()
    manifest_exists = MODEL_MANIFEST.is_file()
    try:
        class_names = labels() if classes_exists else []
        class_error = None
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        class_names = []
        class_error = str(exc)
    try:
        specification_data = model_spec() if manifest_exists else {}
        specification_error = None
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        specification_data = {}
        specification_error = str(exc)
    status = model_status()
    dependencies = block([
        caption_head('Runtime checklist', 'File tồn tại chưa chứng minh model tương thích', ft.Icons.FACT_CHECK),
        dependency_row('Checkpoint PyTorch', 'models/best.pth', checkpoint_exists),
        dependency_row('Thứ tự nhãn', 'models/classes.json', classes_exists),
        dependency_row('Metadata xác minh', 'models/model_manifest.json', manifest_exists),
        dependency_row('Runtime suy luận', 'in-process hoặc runtime tách biệt', status['available']),
        label(status['message'], 11, TEAL if status['available'] else AMBER),
        ft.Container(bgcolor=STATUS_BG, padding=10, border_radius=6, content=label(
            'Chỉ xác nhận sẵn sàng sau khi tải checkpoint thành công và kiểm tra trên tập ảnh độc lập.',
            10, AMBER))], expand=1, padding=14)
    preprocessing = specification_data.get('preprocessing', {})
    resize = preprocessing.get('resize', ['—', '—'])
    architecture = specification_data.get('architecture', '—')
    run_id = specification_data.get('run_id', '—')
    specification = block([
        caption_head('Model specification', 'Đọc từ metadata checkpoint đã xác minh', ft.Icons.MEMORY),
        ft.Row([label('Run', 11), ft.Container(expand=True), label(run_id, 11, WHITE, True)]),
        ft.Row([label('Architecture', 11), ft.Container(expand=True), label(architecture, 11, WHITE, True)]),
        ft.Row([label('Classification classes', 11), ft.Container(expand=True), label(str(len(class_names)), 11, WHITE, True)]),
        ft.Row([label('Input', 11), ft.Container(expand=True), label(f'{resize[0]} × {resize[1]} RGB', 11, WHITE, True)]),
        ft.Row([label('Preprocessing', 11), ft.Container(expand=True),
                label('Resize trực tiếp 224 × 224 • ImageNet normalization', 10, WHITE, True)]),
        *([label(specification_error, 10, AMBER)] if specification_error else []),
        ft.Divider(color=BORDER),
        label('YOLO .pt cần adapter detection riêng; không thể đổi tên thành best.pth.', 11, AMBER),
        label('Checkpoint là file trọng số đã học khi huấn luyện; nó không chứa dataset hay bảo đảm mô hình luôn đúng.', 10),
        label('Chỉ phục vụ nghiên cứu, không thay thế đánh giá của bác sĩ thú y.', 10)],
        expand=1, padding=14)
    class_panel = block([
        caption_head('Thứ tự 10 lớp', 'Đọc từ models/classes.json; đây là thứ tự output của checkpoint.',
                     ft.Icons.LIST_ALT),
        *([label(f'{index}: {name}', 11, WHITE) for index, name in enumerate(class_names)]
          if class_names else [label(class_error or 'Chưa có classes.json từ nhóm AI.', 11, AMBER)])],
        padding=14)
    overall = 'MODEL ĐÃ XÁC MINH • HỖ TRỢ CHUYÊN GIA' if status['available'] else 'CẦN CÀI ĐỦ THÀNH PHẦN'
    heading = ft.Row([ft.Column([label('AI MODEL CONFIGURATION', 10, CYAN, True),
            label('Model readiness', 23, WHITE, True),
            label('Trạng thái file và runtime • chưa thay thế validation model', 11)], spacing=4),
            ft.Container(expand=True), ft.Container(bgcolor=STATUS_BG, padding=9, border_radius=6,
                content=label(overall, 10, TEAL if status['available'] else AMBER, True))])
    return [
        heading,
        ft.Row([dependencies, specification], spacing=10,
               vertical_alignment=ft.CrossAxisAlignment.START),
        class_panel]
