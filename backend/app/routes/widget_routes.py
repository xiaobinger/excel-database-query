"""个性化插件路由"""
import os
import re
import uuid

from flask import Blueprint, current_app, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from app import db
from app.services import widget_service
from app.services.widget_service import WidgetError
from app.utils.auth import get_current_user, login_required

widget_bp = Blueprint('widgets', __name__, url_prefix='/api/widgets')

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}


def _allowed_keys(user):
    return widget_service.get_allowed_widget_keys(user)


def _load_config(user, allowed):
    return widget_service.normalize_config(user.get_widget_config(), allowed)


def _sticker_folder(user_id):
    base_dir = current_app.config.get(
        'UPLOAD_FOLDER',
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads'),
    )
    folder = os.path.join(base_dir, 'widgets', str(user_id))
    os.makedirs(folder, exist_ok=True)
    return folder


def _remove_sticker_file(user_id, image_url):
    match = re.match(r'^/api/widgets/sticker/\d+/([0-9a-fA-F]{32}\.[a-zA-Z0-9]+)$', image_url or '')
    if not match:
        return
    path = os.path.join(_sticker_folder(user_id), secure_filename(match.group(1)))
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


@widget_bp.route('', methods=['GET'])
@login_required
def get_widgets():
    user = get_current_user()
    allowed = _allowed_keys(user)
    return jsonify({
        'success': True,
        'data': {
            'definitions': widget_service.get_definitions(allowed),
            'config': _load_config(user, allowed),
            'is_admin': user.is_admin(),
        },
    })


@widget_bp.route('/config', methods=['PUT'])
@login_required
def save_config():
    user = get_current_user()
    allowed = _allowed_keys(user)
    data = request.get_json() or {}

    current = _load_config(user, allowed)
    settings = {}
    for key, value in (data.get('settings') or {}).items():
        if key in allowed and isinstance(value, dict):
            settings[key] = value
    # 贴图图片只能通过上传接口写入，避免客户端写入任意路径
    incoming_sticker = settings.get('sticker') or {}
    incoming_sticker.pop('image', None)
    settings['sticker'] = incoming_sticker

    merged = {
        'enabled': data.get('enabled', current['enabled']),
        'order': data.get('order', current['order']),
        'collapsed': data.get('collapsed', current['collapsed']),
        'settings': {
            **current['settings'],
            **{k: {**current['settings'].get(k, {}), **v} for k, v in settings.items()},
        },
    }
    config = widget_service.normalize_config(merged, allowed)
    config['settings']['sticker']['image'] = current['settings']['sticker'].get('image', '')

    user.set_widget_config(config)
    db.session.commit()

    return jsonify({'success': True, 'data': {'config': config}})


@widget_bp.route('/weather', methods=['GET'])
@login_required
def get_weather():
    user = get_current_user()
    if 'weather' not in _allowed_keys(user):
        return jsonify({'success': False, 'message': '未授权天气插件'})
    config = _load_config(user, _allowed_keys(user))
    city = request.args.get('city') or config['settings']['weather'].get('city')
    try:
        return jsonify({'success': True, 'data': widget_service.fetch_weather(city)})
    except WidgetError as exc:
        return jsonify({'success': False, 'message': str(exc)})


@widget_bp.route('/news', methods=['GET'])
@login_required
def get_news():
    user = get_current_user()
    if 'news' not in _allowed_keys(user):
        return jsonify({'success': False, 'message': '未授权新闻插件'})
    try:
        # 新闻源统一由管理员在系统配置中维护，普通用户不可修改
        return jsonify({'success': True, 'data': widget_service.fetch_news()})
    except WidgetError as exc:
        return jsonify({'success': False, 'message': str(exc)})


@widget_bp.route('/stocks', methods=['GET'])
@login_required
def get_stocks():
    user = get_current_user()
    if 'stocks' not in _allowed_keys(user):
        return jsonify({'success': False, 'message': '未授权自选股插件'})
    config = _load_config(user, _allowed_keys(user))
    symbols = request.args.get('symbols') or config['settings']['stocks'].get('symbols')
    try:
        return jsonify({'success': True, 'data': widget_service.fetch_stocks(symbols)})
    except WidgetError as exc:
        return jsonify({'success': False, 'message': str(exc)})


@widget_bp.route('/todos', methods=['GET'])
@login_required
def get_todos():
    user = get_current_user()
    if 'todo' not in _allowed_keys(user):
        return jsonify({'success': False, 'message': '未授权待办插件'})
    config = _load_config(user, _allowed_keys(user))
    try:
        limit = int(request.args.get('limit') or config['settings']['todo'].get('limit') or 5)
    except (TypeError, ValueError):
        limit = 5
    data = widget_service.fetch_todos(user, limit)
    return jsonify({'success': True, 'data': data})


@widget_bp.route('/sticker', methods=['POST'])
@login_required
def upload_sticker():
    user = get_current_user()
    if 'sticker' not in _allowed_keys(user):
        return jsonify({'success': False, 'message': '未授权自定义贴图插件'}), 403
    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({'success': False, 'message': '请选择图片文件'}), 400

    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return jsonify({'success': False, 'message': '仅支持 PNG/JPG/GIF/WEBP/BMP 格式'}), 400

    allowed = _allowed_keys(user)
    config = _load_config(user, allowed)
    _remove_sticker_file(user.id, config['settings']['sticker'].get('image', ''))

    filename = f'{uuid.uuid4().hex}.{ext}'
    file.save(os.path.join(_sticker_folder(user.id), filename))
    image_url = f'/api/widgets/sticker/{user.id}/{filename}'
    config['settings']['sticker']['image'] = image_url
    user.set_widget_config(config)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': '贴图已上传',
        'data': {'config': config, 'url': image_url},
    })


@widget_bp.route('/sticker', methods=['DELETE'])
@login_required
def delete_sticker():
    user = get_current_user()
    allowed = _allowed_keys(user)
    config = _load_config(user, allowed)
    _remove_sticker_file(user.id, config['settings']['sticker'].get('image', ''))
    config['settings']['sticker']['image'] = ''
    user.set_widget_config(config)
    db.session.commit()
    return jsonify({'success': True, 'data': {'config': config}})


@widget_bp.route('/sticker/<int:user_id>/<path:filename>', methods=['GET'])
def serve_sticker(user_id, filename):
    return send_from_directory(_sticker_folder(user_id), secure_filename(filename))
