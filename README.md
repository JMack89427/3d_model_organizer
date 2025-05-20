
# 🧠 3D Model Organizer

A Flask web app to upload and manage 3D model files (e.g., .stl) with automatic AI metadata predictions using LLaMA 3 via Ollama — all offline.

---

## 🧾 TL;DR

```bash
# Clone the repo
git clone https://github.com/JMack89427/3d_model_organizer.git
cd 3d_model_organizer

# Install Python deps
pip install -r requirements.txt

# Install Ollama & LLaMA 3
brew install ollama
ollama pull llama3

# Run Flask app
cd app
python 3d_model_organizer.py
```

Go to `http://localhost:5050`, upload a `.stl`, and see predicted creator, filename, and type!

---

## 🚀 Features

- Upload `.stl` files
- Extract geometry metadata (volume, triangles, bounding box)
- Predict:
  - Creator
  - Original filename
  - File type
- Manage entries via UI
- 100% offline using LLaMA 3 + Ollama

---

## 📁 Project Structure

```
.
├── app/
│   ├── 3d_model_organizer.py
│   ├── templates/
├── ai_model/
│   └── ai_metadata_prediction.py
├── uploads/
├── requirements.txt
└── README.md
```

---

## 🧠 Tech Stack

- Flask + Jinja2
- SQLite + SQLAlchemy
- Ollama (local LLM)
- LLaMA 3 (model)
- numpy-stl

---

## ⚙️ Setup

See TL;DR or follow full setup in the main readme section above.

---

## 📚 Future Ideas

- Support .obj, .3mf, .step
- Patreon data lookup for creator matching
- Vector search with FAISS
- User accounts & sharing

---

## 📜 License

GPL3

---
