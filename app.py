import os
from flask import Flask, render_template, request, redirect, url_for, flash, Response, jsonify, send_file
from werkzeug.utils import secure_filename
import cv2
import face_recognition
import numpy as np
from datetime import datetime
import pandas as pd
from fpdf import FPDF
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
UPLOAD_FOLDER = 'Classes'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def is_unique_student_number(class_folder, student_number):
    for filename in os.listdir(class_folder):
        if filename.startswith(student_number):
            return False
    return True

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/capture', methods=['GET', 'POST'])
def capture():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        student_number = request.form['student_number']
        class_name = request.form['class_name'].upper()

        if not all([first_name, last_name, student_number, class_name]):
            flash('All fields are required')
            return redirect(url_for('capture'))

        if not student_number.isdigit() or len(student_number) != 9:
            flash('Student number must be a 9-digit numerical value')
            return redirect(url_for('capture'))

        class_folder = os.path.join(app.config['UPLOAD_FOLDER'], class_name)
        if not os.path.exists(class_folder):
            os.makedirs(class_folder)

        if not is_unique_student_number(class_folder, student_number):
            flash(f'Student number {student_number} already exists in class {class_name}')
            return redirect(url_for('capture'))

        cap = cv2.VideoCapture(0)
        cap.set(3, 640)
        cap.set(4, 480)

        ret, frame = cap.read()
        if not ret:
            flash('Failed to capture image')
            cap.release()
            return redirect(url_for('capture'))

        img_name = f"{student_number}_{first_name}_{last_name}.jpg"
        img_path = os.path.join(class_folder, img_name)
        cv2.imwrite(img_path, frame)
        cap.release()
        flash(f'Image {img_name} saved successfully!')
        return redirect(url_for('capture'))

    return render_template('capture.html')

@app.route('/pick', methods=['GET', 'POST'])
def pick():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        student_number = request.form['student_number']
        class_name = request.form['class_name'].upper()
        file = request.files['file']

        if not all([first_name, last_name, student_number, class_name, file]):
            flash('All fields are required')
            return redirect(url_for('pick'))

        if not student_number.isdigit() or len(student_number) != 9:
            flash('Student number must be a 9-digit numerical value')
            return redirect(url_for('pick'))

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            class_folder = os.path.join(app.config['UPLOAD_FOLDER'], class_name)
            if not os.path.exists(class_folder):
                os.makedirs(class_folder)

            if not is_unique_student_number(class_folder, student_number):
                flash(f'Student number {student_number} already exists in class {class_name}')
                return redirect(url_for('pick'))

            img_name = f"{student_number}_{first_name}_{last_name}{os.path.splitext(filename)[1]}"
            img_path = os.path.join(class_folder, img_name)
            file.save(img_path)
            flash(f'Image {img_name} uploaded successfully!')
        else:
            flash('Invalid file format or no file selected')

        return redirect(url_for('pick'))

    return render_template('pick.html')

@app.route('/select_class', methods=['GET', 'POST'])
def select_class():
    classes = [d for d in os.listdir(app.config['UPLOAD_FOLDER']) if os.path.isdir(os.path.join(app.config['UPLOAD_FOLDER'], d))]
    if request.method == 'POST':
        class_name = request.form['class_name']
        return redirect(url_for('track', class_name=class_name))
    return render_template('select_class.html', classes=classes)

def find_encodings(images):
    encode_list = []
    for img in images:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        try:
            encode = face_recognition.face_encodings(img)[0]
            encode_list.append(encode)
        except IndexError:
            print("Failed to encode face in the image.")
    return encode_list

def mark_attendance(name, class_name):
    filename = f'Attendance_{class_name}.csv'
    with open(filename, 'a+') as f:
        f.seek(0)
        myDataList = f.readlines()
        name_list = [line.split(',')[0] for line in myDataList]
        if name not in name_list:
            now = datetime.now()
            dt_string = now.strftime('%Y-%m-%d %H:%M:%S')
            f.write(f'{name},{dt_string}\n')

@app.route('/video_feed/<class_name>')
def video_feed(class_name):
    return Response(gen_frames(class_name), mimetype='multipart/x-mixed-replace; boundary=frame')

def gen_frames(class_name):
    class_folder = os.path.join(app.config['UPLOAD_FOLDER'], class_name)
    images = []
    classNames = []
    myList = os.listdir(class_folder)
    for cl in myList:
        curImg = cv2.imread(f'{class_folder}/{cl}')
        images.append(curImg)
        classNames.append(os.path.splitext(cl)[0])

    encodeListKnown = find_encodings(images)
    print('Encoding Complete')

    cap = cv2.VideoCapture(0)

    while True:
        success, img = cap.read()
        if not success:
            break

        imgS = cv2.resize(img, (0, 0), None, 0.25, 0.25)
        imgS = cv2.cvtColor(imgS, cv2.COLOR_BGR2RGB)

        facesCurFrame = face_recognition.face_locations(imgS)
        encodesCurFrame = face_recognition.face_encodings(imgS, facesCurFrame)

        for encodeFace, faceLoc in zip(encodesCurFrame, facesCurFrame):
            matches = face_recognition.compare_faces(encodeListKnown, encodeFace)
            faceDis = face_recognition.face_distance(encodeListKnown, encodeFace)
            matchIndex = np.argmin(faceDis)

            if matches[matchIndex] and faceDis[matchIndex] < 0.50:
                name = classNames[matchIndex].upper()
                mark_attendance(name, class_name)
            else:
                name = 'Unknown'

            y1, x2, y2, x1 = faceLoc
            y1, x2, y2, x1 = y1 * 4, x2 * 4, y2 * 4, x1 * 4
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.rectangle(img, (x1, y2 - 35), (x2, y2), (0, 255, 0), cv2.FILLED)
            cv2.putText(img, name, (x1 + 6, y2 - 6), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 255, 255), 2)

        ret, buffer = cv2.imencode('.jpg', img)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    cap.release()

@app.route('/track/<class_name>')
def track(class_name):
    return render_template('track.html', class_name=class_name)

@app.route('/attendance_data/<class_name>')
def attendance_data(class_name):
    filename = f'Attendance_{class_name}.csv'
    data = []
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            for line in f:
                name, time = line.strip().split(',')
                data.append({'name': name, 'time': time})
    return jsonify(data)

@app.route('/export_attendance/<class_name>/<format>')
def export_attendance(class_name, format):
    filename = f'Attendance_{class_name}.csv'
    df = pd.read_csv(filename)
    
    if format == 'pdf':
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font('Arial', size=12)
        for index, row in df.iterrows():
            pdf.cell(200, 10, txt=f"{row['name']} - {row['time']}", ln=True)
        pdf_output = f'Attendance_{class_name}.pdf'
        pdf.output(pdf_output)
        return send_file(pdf_output, as_attachment=True)
    elif format == 'excel':
        excel_output = f'Attendance_{class_name}.xlsx'
        df.to_excel(excel_output, index=False)
        return send_file(excel_output, as_attachment=True)
    else:
        return jsonify({"error": "Invalid format"}), 400

@app.route('/manage_classes', methods=['GET', 'POST'])
def manage_classes():
    if request.method == 'POST':
        class_name = request.form['class_name'].upper()
        file = request.files['file']

        if not class_name:
            flash('Class name is required')
            return redirect(url_for('manage_classes'))

        if not file or not allowed_file(file.filename):
            flash('A valid file is required')
            return redirect(url_for('manage_classes'))

        filename = secure_filename(file.filename)
        class_folder = os.path.join(app.config['UPLOAD_FOLDER'], class_name)
        
        if not os.path.exists(class_folder):
            os.makedirs(class_folder)

        file.save(os.path.join(class_folder, filename))
        flash(f'Class {class_name} and file {filename} have been uploaded successfully!')

        return redirect(url_for('manage_classes'))

    return render_template('manage_classes.html')

@app.route('/add_class_member', methods=['POST'])
def add_class_member():
    # Handle form submission to add a new class member
    return redirect(url_for('manage_classes'))  # Redirect to manage_classes route after adding member

@app.route('/send_email/<class_name>', methods=['POST'])
def send_email(class_name):
    email = request.form.get('email')
    filename = f'Attendance_{class_name}.csv'
    subject = f'Attendance for {class_name}'
    body = f'Please find the attached attendance file for class {class_name}.'

    msg = MIMEMultipart()
    msg['From'] = os.getenv('EMAIL_USER')
    msg['To'] = email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    attachment = MIMEApplication(open(filename, "rb").read())
    attachment.add_header('Content-Disposition', 'attachment', filename=filename)
    msg.attach(attachment)

    server = smtplib.SMTP(os.getenv('SMTP_SERVER'), int(os.getenv('SMTP_PORT')))
    server.starttls()
    server.login(os.getenv('EMAIL_USER'), os.getenv('EMAIL_PASSWORD'))
    server.send_message(msg)
    server.quit()

    return jsonify({"message": "Email sent successfully!"})

if __name__ == "__main__":
    app.run(debug=True)
