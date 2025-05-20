from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os
from waitress import serve

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///models.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Create the upload directory if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

class Model(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    creator = db.Column(db.String(80), nullable=False)
    model = db.Column(db.String(120), nullable=False)
    file_type = db.Column(db.String(20), nullable=False)
    filename = db.Column(db.String(120), nullable=False)

@app.route('/')
def index():
    return render_template('index.html')  # Remove 'templates/' prefix

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400
    
    file = request.files['file']
    creator = request.form.get('creator')
    model = request.form.get('model')
    file_type = request.form.get('file_type')

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if not creator or not model or not file_type:
        return jsonify({'error': 'Missing directory information'}), 400
    
    filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filename)

    new_model = Model(creator=creator, model=model, file_type=file_type, filename=file.filename)
    db.session.add(new_model)
    db.session.commit()

    return jsonify({'success': 'File successfully uploaded'}), 201

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

def create_app_context():
    with app.app_context():
        db.create_all()

if __name__ == '__main__':
    create_app_context()
    app.run(host='0.0.0.0', port=5050, debug=True)