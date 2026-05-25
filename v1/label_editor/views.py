import json
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST
from .models import LabelLayout, EditorImage
from v1.label.models import MyLabel


def _get_label_or_404(label_id, user):
    return get_object_or_404(MyLabel, pk=label_id, user=user)


@login_required
@require_http_methods(['GET'])
def layout_get(request, label_id):
    label = _get_label_or_404(label_id, request.user)
    layout, _ = LabelLayout.objects.get_or_create(label=label)
    return JsonResponse({
        'success': True,
        'data': {
            'canvas_width': layout.canvas_width,
            'canvas_height': layout.canvas_height,
            'grid_size': layout.grid_size,
            'background_color': layout.background_color,
            'elements': layout.elements,
        }
    })


@login_required
@require_POST
def layout_save(request, label_id):
    label = _get_label_or_404(label_id, request.user)
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': '잘못된 요청입니다.'}, status=400)

    layout, _ = LabelLayout.objects.get_or_create(label=label)
    layout.canvas_width = int(body.get('canvas_width', layout.canvas_width))
    layout.canvas_height = int(body.get('canvas_height', layout.canvas_height))
    layout.grid_size = int(body.get('grid_size', layout.grid_size))
    layout.background_color = body.get('background_color', layout.background_color)
    layout.elements = body.get('elements', layout.elements)
    layout.save()
    return JsonResponse({'success': True})


@login_required
@require_POST
def image_upload(request, label_id):
    label = _get_label_or_404(label_id, request.user)
    image_file = request.FILES.get('image')
    if not image_file:
        return JsonResponse({'success': False, 'error': '이미지 파일이 없습니다.'}, status=400)
    if image_file.size > 5 * 1024 * 1024:
        return JsonResponse({'success': False, 'error': '5MB 이하 이미지만 업로드 가능합니다.'}, status=400)

    img = EditorImage.objects.create(
        label=label,
        file=image_file,
        original_filename=image_file.name,
    )
    return JsonResponse({
        'success': True,
        'data': {
            'id': img.pk,
            'url': request.build_absolute_uri(img.file.url),
            'filename': img.original_filename,
        }
    })


@login_required
@require_http_methods(['GET'])
def image_list(request, label_id):
    label = _get_label_or_404(label_id, request.user)
    images = EditorImage.objects.filter(label=label).order_by('-uploaded_datetime')
    return JsonResponse({
        'success': True,
        'data': [
            {
                'id': img.pk,
                'url': request.build_absolute_uri(img.file.url),
                'filename': img.original_filename,
            }
            for img in images
        ]
    })
