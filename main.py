import cv2
import dlib
import pygame
import numpy as np
import time
import sqlite3
from scipy.spatial import distance as dist
from datetime import datetime
import smtplib
from email.message import EmailMessage
import requests
import mediapipe as mp


pygame.mixer.init()
alarm_sound = pygame.mixer.Sound(r"c:\Users\USER\Desktop\Projects\تخرج\صوت إنذار ٢ صوت مزعج(MP3_320K).mp3")


detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor(r"c:\Users\USER\Desktop\Projects\تخرج\shape_predictor_68_face_landmarks.dat")


conn = sqlite3.connect("distractions.db")
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS distractions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT,
        start_time TEXT,
        end_time TEXT,
        duration REAL,
        location TEXT
    )
''')
conn.commit()


mp_hands = mp.solutions.hands
hands = mp_hands.Hands(static_image_mode=False,
                       max_num_hands=2,
                       min_detection_confidence=0.5,
                       min_tracking_confidence=0.5)
mp_draw = mp.solutions.drawing_utils


email_notification_time = None
telegram_notification_time = None
NOTIFICATION_DURATION = 5.0  


def get_current_location():
    url = "http://ipinfo.io/json"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            city = data.get('city', 'غير معروف')
            country = data.get('country', 'غير معروف')
            return f"{city}, {country}"
        else:
            return "غير معروف"
    except Exception as e:
        print("❌ خطأ في الحصول على الموقع:", e)
        return "غير معروف"


def send_email_notification(distraction_type, start_time, end_time, duration, location):
    global email_notification_time
    msg = EmailMessage()
    msg['Subject'] = '🚨 تنبيه: تم رصد حالة تشتت'
    msg['From'] = 'Nidal123ln@gmail.com'
    msg['To'] = 'nidal12saleh@gmail.com'
    msg.set_content(f"""
🚗 تم رصد حالة تشتت:
النوع: {distraction_type}
من: {start_time}
إلى: {end_time}
المدة: {duration} ثانية
الموقع: {location}
""")
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login('Nidal123ln@gmail.com', 'wsrb biaw uekm zbvh')
            smtp.send_message(msg)
            print("✅ تم إرسال التنبيه إلى البريد الإلكتروني بنجاح.")
            email_notification_time = time.time()  
    except Exception as e:
        print("❌ فشل إرسال البريد:", e)

def send_telegram_message(distraction_type, start_time, end_time, duration, location):
    global telegram_notification_time
    token = '7547616033:AAF6Mhdy0ma0rETUqP474LW03CsDvNTclfU'
    chat_id = '960702798'
    message = f"""
🚗 تم رصد حالة تشتت:
النوع: {distraction_type}
من: {start_time}
إلى: {end_time}
المدة: {duration} ثانية
الموقع: {location}
"""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            print("✅ تم إرسال الإشعار إلى تيليجرام")
            telegram_notification_time = time.time()  
        else:
            print("❌ فشل إرسال تيليجرام: استجابة غير ناجحة")
    except Exception as e:
        print("❌ خطأ في إرسال تيليجرام:", e)

def log_distraction(distraction_type, start, end):
    duration = round(end - start, 2)
    start_time = datetime.fromtimestamp(start).strftime('%Y-%m-%d %H:%M:%S')
    end_time = datetime.fromtimestamp(end).strftime('%Y-%m-%d %H:%M:%S')
    location = get_current_location()

    cursor.execute('''
        INSERT INTO distractions (type, start_time, end_time, duration, location)
        VALUES (?, ?, ?, ?, ?)
    ''', (distraction_type, start_time, end_time, duration, location))
    conn.commit()

    send_email_notification(distraction_type, start_time, end_time, duration, location)
    send_telegram_message(distraction_type, start_time, end_time, duration, location)

def eye_aspect_ratio(eye):
    A = dist.euclidean(eye[1], eye[5])
    B = dist.euclidean(eye[2], eye[4])
    C = dist.euclidean(eye[0], eye[3])
    return (A + B) / (2.0 * C)

def mouth_aspect_ratio(mouth):
    A = dist.euclidean(mouth[13], mouth[19])
    B = dist.euclidean(mouth[14], mouth[18])
    C = dist.euclidean(mouth[15], mouth[17])
    return (A + B + C) / 3.0

def get_head_pose(shape, frame):
    image_points = np.array([
        (shape[30][0], shape[30][1]),
        (shape[8][0], shape[8][1]),
        (shape[36][0], shape[36][1]),
        (shape[45][0], shape[45][1]),
        (shape[48][0], shape[48][1]),
        (shape[54][0], shape[54][1])
    ], dtype="double")

    model_points = np.array([
        (0.0, 0.0, 0.0),
        (0.0, -330.0, -65.0),
        (-225.0, 170.0, -135.0),
        (225.0, 170.0, -135.0),
        (-150.0, -150.0, -125.0),
        (150.0, -150.0, -125.0)
    ])

    focal_length = frame.shape[1]
    center = (frame.shape[1]/2, frame.shape[0]/2)
    camera_matrix = np.array([
        [focal_length, 0, center[0]],
        [0, focal_length, center[1]],
        [0, 0, 1]
    ], dtype="double")

    dist_coeffs = np.zeros((4,1))
    _, rotation_vector, translation_vector = cv2.solvePnP(model_points, image_points, camera_matrix, dist_coeffs)
    rotation_mat, _ = cv2.Rodrigues(rotation_vector)
    pose_mat = cv2.hconcat((rotation_mat, translation_vector))
    _, _, _, _, _, _, euler_angles = cv2.decomposeProjectionMatrix(pose_mat)
    return euler_angles


EYE_AR_THRESH = 0.22
HEAD_POSE_THRESH = 30
MAR_THRESH = 10
DISTRACTION_DELAY = 2.0
ALARM_ON = False
distraction_start_time = None
current_distraction_type = None


prev_frame_time = 0
new_frame_time = 0

cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    

    new_frame_time = time.time()
    fps = 1 / (new_frame_time - prev_frame_time) if prev_frame_time != 0 else 0
    prev_frame_time = new_frame_time


    if not ret:
        
        break

    current_time = time.time()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = detector(gray)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    hand_results = hands.process(rgb_frame)
    num_hands = len(hand_results.multi_hand_landmarks) if hand_results.multi_hand_landmarks else 0

    for face in faces:
        landmarks = predictor(gray, face)
        landmarks = [(p.x, p.y) for p in landmarks.parts()]

        left_eye = landmarks[42:48]
        right_eye = landmarks[36:42]
        mouth = landmarks[48:68]

        left_ear = eye_aspect_ratio(left_eye)
        right_ear = eye_aspect_ratio(right_eye)
        ear = (left_ear + right_ear) / 2.0
        mar = mouth_aspect_ratio(mouth)
        yaw, roll = get_head_pose(landmarks, frame)[1:]

        distraction_detected = False
        new_distraction_type = None

        if ear < EYE_AR_THRESH:
            new_distraction_type = "eyes_closed"
            distraction_detected = True
        elif abs(yaw) > HEAD_POSE_THRESH:
            new_distraction_type = "head_pose"
            distraction_detected = True
        elif mar > MAR_THRESH:
            new_distraction_type = "yawning"
            distraction_detected = True
        elif num_hands == 1 or num_hands == 2:
            new_distraction_type = "distracted_hands"
            distraction_detected = True

        if distraction_detected:
            if distraction_start_time is None:
                distraction_start_time = current_time
            else:
                elapsed_time = current_time - distraction_start_time
                # if elapsed_time >= DISTRACTION_DELAY and not ALARM_ON:
                #     ALARM_ON = True
                #     alarm_sound.play()
                #     current_distraction_type = new_distraction_type
                if elapsed_time >= DISTRACTION_DELAY:
                    if not ALARM_ON:
                        ALARM_ON = True
                        alarm_sound.play()
                        current_distraction_type = new_distraction_type
                    else:
                        # إذا التشتت مستمر والصوت توقف لأي سبب، نعيد تشغيله
                        if not pygame.mixer.get_busy():
                            alarm_sound.play()
        else:
            if ALARM_ON:
                ALARM_ON = False
                alarm_sound.stop()
                if current_distraction_type:
                    log_distraction(current_distraction_type, distraction_start_time, current_time)
            distraction_start_time = None
            current_distraction_type = None

        cv2.putText(frame, f"EAR: {ear:.2f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
        cv2.putText(frame, f"Yaw: {int(yaw)}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
        cv2.putText(frame, f"MAR: {mar:.2f}", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
        cv2.putText(frame, f"Hands: {num_hands}", (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
        cv2.putText(frame, f"FPS: {int(fps)}", (10, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    if ALARM_ON:
        cv2.putText(frame, "ALARM: ON", (frame.shape[1]-150, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    if email_notification_time and (current_time - email_notification_time) <= NOTIFICATION_DURATION:
        cv2.putText(frame, "A notification has been sent to your mail.", (10, frame.shape[0] - 60),
                    cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 255, 0), 2)

    if telegram_notification_time and (current_time - telegram_notification_time) <= NOTIFICATION_DURATION:
        cv2.putText(frame, "A notification has been sent to Telegram", (10, frame.shape[0] - 30),
                    cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 255, 0), 2)

    if hand_results.multi_hand_landmarks:
        for hand_landmarks in hand_results.multi_hand_landmarks:
            mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

    cv2.imshow("Driver Monitoring System", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        if ALARM_ON and current_distraction_type:
            log_distraction(current_distraction_type, distraction_start_time, current_time)
        break

cap.release()
cv2.destroyAllWindows()
conn.close()
