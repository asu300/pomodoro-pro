import os
import uuid
import time
import json
import base64
import replicate
import requests
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO

load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100MB

UPLOAD_DIR = Path("uploads")
RESULT_DIR = Path("results")
UPLOAD_DIR.mkdir(exist_ok=True)
RESULT_DIR.mkdir(exist_ok=True)

ALLOWED_EXT = {"png", "jpg", "jpeg", "webp"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def url_to_file(url, save_path):
    """Download result image from URL."""
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    with open(save_path, "wb") as f:
        f.write(r.content)
    return save_path


def file_to_data_uri(path):
    """Convert local file to data URI."""
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    ext = path.suffix.lower().lstrip(".")
    mime = {"jpg": "jpeg"}.get(ext, ext)
    return f"data:image/{mime};base64,{data}"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/upload", methods=["POST"])
def upload():
    """Upload style reference images or target photo."""
    files = request.files.getlist("files")
    category = request.form.get("category", "style")  # 'style' or 'target'

    saved = []
    for f in files:
        if f and allowed_file(f.filename):
            name = f"{uuid.uuid4().hex[:12]}.{f.filename.rsplit('.', 1)[1].lower()}"
            path = UPLOAD_DIR / name
            f.save(path)
            # Generate thumbnail
            try:
                img = Image.open(path)
                img.thumbnail((300, 300))
                thumb_path = UPLOAD_DIR / f"thumb_{name}"
                img.save(thumb_path, quality=85)
            except Exception:
                pass
            saved.append({
                "id": name.split(".")[0],
                "filename": name,
                "url": f"/uploads/{name}",
                "thumb": f"/uploads/thumb_{name}",
            })

    return jsonify({"ok": True, "files": saved})


@app.route("/api/transfer", methods=["POST"])
def transfer():
    """Run style transfer."""
    data = request.json
    style_ids = data.get("style_ids", [])
    target_id = data.get("target_id")
    mode = data.get("mode", "fast")  # 'fast' or 'detail'
    strength = data.get("strength", 0.65)

    if not style_ids or not target_id:
        return jsonify({"ok": False, "error": "请上传风格参考图和目标照片"}), 400

    token = os.getenv("REPLICATE_API_TOKEN")
    if not token:
        return jsonify({"ok": False, "error": "请在 .env 中配置 REPLICATE_API_TOKEN"}), 500

    # Find target file
    target_files = list(UPLOAD_DIR.glob(f"{target_id}.*"))
    if not target_files:
        return jsonify({"ok": False, "error": "目标照片未找到"}), 400
    target_path = target_files[0]

    # Use first style image as primary reference
    style_files = []
    for sid in style_ids:
        matches = list(UPLOAD_DIR.glob(f"{sid}.*"))
        if matches and "thumb_" not in matches[0].name:
            style_files.append(matches[0])

    if not style_files:
        return jsonify({"ok": False, "error": "风格参考图未找到"}), 400

    style_path = style_files[0]

    try:
        if mode == "fast":
            result_url = _transfer_fast(token, target_path, style_path, strength)
        else:
            result_url = _transfer_detail(token, target_path, style_path, style_files, strength)

        # Save result
        result_name = f"result_{uuid.uuid4().hex[:8]}.png"
        result_path = RESULT_DIR / result_name
        url_to_file(result_url, result_path)

        return jsonify({
            "ok": True,
            "result": f"/results/{result_name}",
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def _transfer_fast(token, target_path, style_path, strength):
    """Fast style transfer using PyTorch NST model."""
    with open(target_path, "rb") as content, open(style_path, "rb") as style:
        output = replicate.run(
            "daanelson/art-attack:564445353695486789ae5e86ab48507851dbed59bf1a0f3b26e3b3d4f1e9b380",
            input={
                "content": content,
                "style": style,
                "alpha": strength,
            },
            api_token=token,
        )
    return str(output)


def _transfer_detail(token, target_path, style_path, all_styles, strength):
    """Detail mode: use SD img2img with style guidance."""
    with open(target_path, "rb") as img:
        output = replicate.run(
            "stability-ai/sdxl:7762fd07cf82c949c63f29cd0412eb547371d7b8b4bb4af0dce8de4a6ab981ec",
            input={
                "image": img,
                "prompt": "in the artistic painting style, masterful brushwork, oil painting texture",
                "negative_prompt": "photograph, realistic photo, blurry, low quality, deformed",
                "strength": max(0.3, strength - 0.1),
                "guidance_scale": 9.0,
                "num_inference_steps": 30,
                "width": 1024,
                "height": 1024,
            },
            api_token=token,
        )
    return str(output[0]) if isinstance(output, list) else str(output)


@app.route("/api/train", methods=["POST"])
def train():
    """Train a LoRA on uploaded style images (advanced mode)."""
    data = request.json
    style_ids = data.get("style_ids", [])
    artist_name = data.get("artist_name", "custom")
    trigger_word = data.get("trigger_word", "sks style")

    token = os.getenv("REPLICATE_API_TOKEN")
    if not token:
        return jsonify({"ok": False, "error": "请在 .env 中配置 REPLICATE_API_TOKEN"}), 500

    # Collect style images as data URIs
    images = []
    for sid in style_ids:
        matches = list(UPLOAD_DIR.glob(f"{sid}.*"))
        if matches and "thumb_" not in matches[0].name:
            images.append(file_to_data_uri(matches[0]))

    if len(images) < 5:
        return jsonify({"ok": False, "error": "至少需要 5 张风格参考图来训练"}), 400

    try:
        training = replicate.trainings.create(
            "ostris/flux-dev-lora-trainer",
            "c22494b26a06b41d47f3b8e4c1d8f0e3d3c8e9b0a4d1e2f3a4b5c6d7e8f9a0b1",
            input={
                "input_images": images,
                "trigger_word": trigger_word,
                "lora_rank": 16,
                "autocaption": True,
            },
            destination=f"asu300/{artist_name}-style",
        )

        return jsonify({
            "ok": True,
            "training_id": training.id,
            "status": training.status,
            "message": f"训练已启动，ID: {training.id}。训练约需 15-30 分钟。",
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/train/status/<training_id>")
def train_status(training_id):
    """Check LoRA training status."""
    token = os.getenv("REPLICATE_API_TOKEN")
    try:
        training = replicate.trainings.get(training_id)
        result = {
            "id": training.id,
            "status": training.status,
        }
        if training.status == "succeeded":
            result["model"] = training.output.get("version", "")
            result["message"] = "训练完成！可以使用该模型进行风格迁移了。"
        elif training.status == "failed":
            result["message"] = f"训练失败: {training.error}"
        else:
            result["message"] = f"训练中... 状态: {training.status}"
        return jsonify({"ok": True, **result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/generate/lora", methods=["POST"])
def generate_lora():
    """Generate using a trained LoRA model."""
    data = request.json
    model_version = data.get("model_version")
    target_id = data.get("target_id")
    trigger_word = data.get("trigger_word", "sks style")
    strength = data.get("strength", 0.8)

    token = os.getenv("REPLICATE_API_TOKEN")
    if not token:
        return jsonify({"ok": False, "error": "请配置 API Token"}), 500

    target_files = list(UPLOAD_DIR.glob(f"{target_id}.*"))
    if not target_files:
        return jsonify({"ok": False, "error": "目标照片未找到"}), 400

    try:
        with open(target_files[0], "rb") as img:
            output = replicate.run(
                model_version,
                input={
                    "image": img,
                    "prompt": f"{trigger_word} style, artistic painting, masterful artwork",
                    "negative_prompt": "photo, realistic, blurry, low quality",
                    "strength": strength,
                    "guidance_scale": 7.5,
                    "num_inference_steps": 28,
                },
                api_token=token,
            )

        result_url = str(output[0]) if isinstance(output, list) else str(output)
        result_name = f"lora_{uuid.uuid4().hex[:8]}.png"
        result_path = RESULT_DIR / result_name
        url_to_file(result_url, result_path)

        return jsonify({"ok": True, "result": f"/results/{result_name}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/results/<path:filename>")
def serve_result(filename):
    return send_from_directory(RESULT_DIR, filename)


@app.route("/api/files")
def list_files():
    """List uploaded files."""
    style_files = []
    target_files = []
    for f in UPLOAD_DIR.iterdir():
        if f.name.startswith("thumb_"):
            continue
        info = {
            "id": f.stem,
            "filename": f.name,
            "url": f"/uploads/{f.name}",
            "thumb": f"/uploads/thumb_{f.name}" if (UPLOAD_DIR / f"thumb_{f.name}").exists() else f"/uploads/{f.name}",
        }
        style_files.append(info)
    return jsonify({"ok": True, "files": style_files})


@app.route("/api/delete/<file_id>", methods=["DELETE"])
def delete_file(file_id):
    """Delete an uploaded file."""
    for f in UPLOAD_DIR.glob(f"{file_id}.*"):
        f.unlink(missing_ok=True)
    return jsonify({"ok": True})


if __name__ == "__main__":
    print("=== AI 风格迁移工具 ===")
    print("请确保已配置 REPLICATE_API_TOKEN 到 .env 文件")
    print("访问 http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)
