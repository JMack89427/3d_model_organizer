import os
import json
import subprocess
from stl import mesh
from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from duckduckgo_search import DDGS

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///models.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Ensure upload directory exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

class Model(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    creator = db.Column(db.String(80), nullable=False)
    model = db.Column(db.String(120), nullable=False)
    file_type = db.Column(db.String(20), nullable=False)
    filename = db.Column(db.String(120), nullable=False)

def web_enrich_prompt(filename):
    try:
        query = filename.replace('_', ' ').replace('-', ' ')
        search_terms = f"{query} site:patreon.com OR site:thingiverse.com OR site:printables.com"
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(search_terms, max_results=5):
                results.append(f"{r['title']}: {r['body']}")
        return "\n".join(results)
    except Exception as e:
        return f"(Web enrichment failed: {str(e)})"

def extract_stl_metadata(filepath):
    try:
        model = mesh.Mesh.from_file(filepath)
        num_triangles = len(model)
        min_ = model.min_.tolist()
        max_ = model.max_.tolist()
        volume = model.get_mass_properties()[0]

        return {
            "num_triangles": num_triangles,
            "bounding_box_min": min_,
            "bounding_box_max": max_,
            "volume": volume,
            "filename": os.path.basename(filepath)
        }
    except Exception as e:
        return {"error": f"Failed to parse STL: {str(e)}"}

def call_local_llm(metadata_dict):
    web_context = web_enrich_prompt(metadata_dict.get("filename", "3d model"))
    prompt = f"""
Use the following web results to help answer:

{web_context}

Then, using this metadata:

{json.dumps(metadata_dict, indent=2)}

Predict:
- Creator
- Original filename
- File type

Return JSON with: creator, filename, filetype.
"""
    try:
        result = subprocess.run(
            ["ollama", "run", "llama3"],
            input=prompt.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30
        )

        if result.returncode != 0:
            return {"error": result.stderr.decode("utf-8")}

        response = result.stdout.decode("utf-8")

        # Try to extract JSON from response
        start = response.find('{')
        end = response.rfind('}') + 1
        json_str = response[start:end]
        llm_response = json.loads(json_str)
        return {
            "llm_response": llm_response,
            "web_context": web_context,
            "prompt": prompt,
            "raw_response": response
        }

    except Exception as e:
        return {"error": f"LLM call failed: {str(e)}"}

def analyze_stl(filepath):
    metadata = extract_stl_metadata(filepath)
    if "error" in metadata:
        return metadata

    result = call_local_llm(metadata)
    if "error" in result:
        return result

    # Merge LLM response and context fields for template
    return {
        **result["llm_response"],
        "web_context": result["web_context"],
        "prompt": result["prompt"],
        "raw_response": result["raw_response"]
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filename)

    prediction = analyze_stl(filename)

    if 'error' in prediction:
        return jsonify({'error': prediction['error']}), 500

    return render_template(
        'confirm.html',
        creator=prediction.get('creator', 'Unknown'),
        model_name=prediction.get('filename', file.filename),
        file_type=prediction.get('filetype', 'Unknown'),
        filename=file.filename,
        web_context=prediction.get('web_context', ''),
        prompt_data=prediction.get('prompt', ''),
        llm_response=prediction.get('raw_response', '')
    )

@app.route('/confirm', methods=['POST'])
def confirm_prediction():
    creator = request.form.get('creator')
    model_name = request.form.get('model_name')
    file_type = request.form.get('file_type')
    filename = request.form.get('filename')

    new_model = Model(creator=creator, model=model_name, file_type=file_type, filename=filename)
    db.session.add(new_model)
    db.session.commit()

    return redirect(url_for('manage_entries'))

@app.route('/manage')
def manage_entries():
    models = Model.query.all()
    return render_template('manage.html', models=models)

@app.route('/add', methods=['POST'])
def add_entry():
    creator = request.form.get('creator')
    model = request.form.get('model')
    file_type = request.form.get('file_type')
    filename = request.form.get('filename')

    new_model = Model(creator=creator, model=model, file_type=file_type, filename=filename)
    db.session.add(new_model)
    db.session.commit()

    return redirect(url_for('manage_entries'))

@app.route('/delete/<int:id>', methods=['POST'])
def delete_entry(id):
    model = Model.query.get(id)
    if model:
        db.session.delete(model)
        db.session.commit()
    return redirect(url_for('manage_entries'))

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=True)
