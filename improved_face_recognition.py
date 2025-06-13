#!/usr/bin/env python3
"""
Module nhận diện khuôn mặt cải tiến cho Raspberry Pi 5
Sử dụng OpenCV DNN với MobileNet SSD cho hiệu suất cao
"""

import cv2
import numpy as np
import pickle
import os
import logging
import time
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class FaceDetectionResult:
    """Kết quả phát hiện khuôn mặt"""
    detected: bool = False
    recognized: bool = False
    confidence: float = 0.0
    bbox: Tuple[int, int, int, int] = (0, 0, 0, 0)  # (x, y, w, h)
    person_name: str = ""
    message: str = ""

class ImprovedFaceRecognition:
    """
    Nhận diện khuôn mặt cải tiến với:
    - OpenCV DNN cho detection nhanh
    - LBPH cho recognition
    - Bounding boxes với màu sắc
    - FPS cao, optimized cho Pi 5
    """
    
    def __init__(self, 
                 models_path: str = "/home/khoi/Desktop/KHOI_LUANAN/models",
                 face_data_path: str = "/home/khoi/Desktop/KHOI_LUANAN/face_data",
                 confidence_threshold: float = 0.5,
                 recognition_threshold: float = 100.0):
        
        self.models_path = models_path
        self.face_data_path = face_data_path
        self.confidence_threshold = confidence_threshold
        self.recognition_threshold = recognition_threshold
        
        # Tạo thư mục nếu chưa có
        os.makedirs(self.models_path, exist_ok=True)
        os.makedirs(self.face_data_path, exist_ok=True)
        
        # Face detector và recognizer
        self.face_net = None
        self.face_recognizer = None
        self.face_cascade = None  # Backup method
        self.known_faces_db = {}
        
        # Performance settings
        self.input_size = (300, 300)
        self.scale_factor = 0.7  # Scale down for speed
        
        self._initialize_models()
        self._load_face_database()
        
        logger.info("✅ ImprovedFaceRecognition khởi tạo thành công!")
    
    def _initialize_models(self):
        """Khởi tạo các mô hình AI"""
        try:
            # Đường dẫn files
            prototxt_path = os.path.join(self.models_path, "deploy.prototxt")
            weights_path = os.path.join(self.models_path, "res10_300x300_ssd_iter_140000.caffemodel")
            
            # Kiểm tra files tồn tại
            if os.path.exists(prototxt_path) and os.path.exists(weights_path):
                try:
                    # Load DNN model
                    self.face_net = cv2.dnn.readNetFromCaffe(prototxt_path, weights_path)
                    self.face_net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                    self.face_net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                    logger.info("✅ DNN Face Detection model loaded")
                except Exception as e:
                    logger.warning(f"⚠️ Không load được DNN model: {e}")
                    self.face_net = None
            else:
                logger.warning("⚠️ Chưa có DNN model files")
                self.face_net = None
            
            # Backup: Haar Cascade
            try:
                cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                self.face_cascade = cv2.CascadeClassifier(cascade_path)
                logger.info("✅ Haar Cascade backup loaded")
            except Exception as e:
                logger.error(f"❌ Không load được Haar Cascade: {e}")
                raise
            
            # Face recognizer - LBPH
            try:
                self.face_recognizer = cv2.face.LBPHFaceRecognizer_create(
                    radius=1,
                    neighbors=8,
                    grid_x=8,
                    grid_y=8,
                    threshold=self.recognition_threshold
                )
                logger.info("✅ LBPH Face Recognizer created")
            except Exception as e:
                logger.error(f"❌ Không tạo được face recognizer: {e}")
                raise
            
        except Exception as e:
            logger.error(f"❌ Lỗi khởi tạo models: {e}")
            raise
    
    def _load_face_database(self):
        """Load database khuôn mặt"""
        try:
            db_file = os.path.join(self.face_data_path, "face_database.pkl")
            
            if os.path.exists(db_file):
                with open(db_file, 'rb') as f:
                    self.known_faces_db = pickle.load(f)
                
                # Train recognizer nếu có dữ liệu
                if self.known_faces_db:
                    self._train_recognizer()
                    logger.info(f"✅ Loaded {len(self.known_faces_db)} people from database")
                else:
                    logger.info("ℹ️ Database trống, chưa có ai được đăng ký")
            else:
                logger.info("ℹ️ Chưa có database, sẽ tạo mới khi cần")
                self.known_faces_db = {}
                
        except Exception as e:
            logger.error(f"❌ Lỗi load database: {e}")
            self.known_faces_db = {}
    
    def _train_recognizer(self):
        """Train lại face recognizer với dữ liệu hiện có"""
        try:
            if not self.known_faces_db:
                return
            
            faces = []
            labels = []
            
            for person_id, person_data in enumerate(self.known_faces_db.values()):
                for face_encoding in person_data['faces']:
                    faces.append(face_encoding)
                    labels.append(person_id)
            
            if faces:
                self.face_recognizer.train(faces, np.array(labels))
                logger.info(f"✅ Trained recognizer với {len(faces)} faces từ {len(self.known_faces_db)} người")
            
        except Exception as e:
            logger.error(f"❌ Lỗi train recognizer: {e}")
    
    def detect_faces_dnn(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Detect faces using DNN"""
        try:
            h, w = frame.shape[:2]
            
            # Tạo blob cho DNN
            blob = cv2.dnn.blobFromImage(frame, 1.0, self.input_size, 
                                       [104, 117, 123], False, False)
            self.face_net.setInput(blob)
            detections = self.face_net.forward()
            
            faces = []
            for i in range(detections.shape[2]):
                confidence = detections[0, 0, i, 2]
                
                if confidence > self.confidence_threshold:
                    box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                    (x, y, x1, y1) = box.astype("int")
                    
                    # Đảm bảo tọa độ hợp lệ
                    x = max(0, x)
                    y = max(0, y)
                    w_box = min(w - x, x1 - x)
                    h_box = min(h - y, y1 - y)
                    
                    if w_box > 30 and h_box > 30:  # Kích thước tối thiểu
                        faces.append((x, y, w_box, h_box))
            
            return faces
            
        except Exception as e:
            logger.error(f"Lỗi DNN detection: {e}")
            return []
    
    def detect_faces_haar(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Detect faces using Haar Cascade (backup method)"""
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Scale down để tăng tốc
            h, w = gray.shape
            small_gray = cv2.resize(gray, None, fx=self.scale_factor, fy=self.scale_factor)
            
            faces = self.face_cascade.detectMultiScale(
                small_gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(20, 20),
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            
            # Scale back về kích thước gốc
            scaled_faces = []
            for (x, y, w, h) in faces:
                x = int(x / self.scale_factor)
                y = int(y / self.scale_factor)
                w = int(w / self.scale_factor)
                h = int(h / self.scale_factor)
                scaled_faces.append((x, y, w, h))
            
            return scaled_faces
            
        except Exception as e:
            logger.error(f"Lỗi Haar detection: {e}")
            return []
    
    def detect_faces(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Main face detection method"""
        # Thử DNN trước, nếu không được thì dùng Haar
        if self.face_net is not None:
            faces = self.detect_faces_dnn(frame)
            if faces:
                return faces
        
        # Fallback to Haar
        return self.detect_faces_haar(frame)
    
    def recognize_face(self, frame: np.ndarray, face_bbox: Tuple[int, int, int, int]) -> Tuple[str, float]:
        """Nhận diện khuôn mặt"""
        try:
            if not self.known_faces_db:
                return "Unknown", 0.0
            
            x, y, w, h = face_bbox
            
            # Đảm bảo ROI hợp lệ
            x = max(0, x)
            y = max(0, y)
            w = min(w, frame.shape[1] - x)
            h = min(h, frame.shape[0] - y)
            
            if w <= 0 or h <= 0:
                return "Unknown", 0.0
            
            # Extract face ROI
            face_roi = frame[y:y+h, x:x+w]
            
            if face_roi.size == 0:
                return "Unknown", 0.0
            
            # Preprocess
            gray_face = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
            gray_face = cv2.resize(gray_face, (100, 100))
            gray_face = cv2.equalizeHist(gray_face)  # Improve lighting
            
            # Predict
            label, confidence = self.face_recognizer.predict(gray_face)
            
            # Get person name từ label
            if confidence < self.recognition_threshold and label < len(self.known_faces_db):
                person_names = list(self.known_faces_db.keys())
                return person_names[label], confidence
            else:
                return "Unknown", confidence
                
        except Exception as e:
            logger.error(f"Lỗi recognize face: {e}")
            return "Unknown", 0.0
    
    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, FaceDetectionResult]:
        """
        Xử lý frame chính với detection và recognition
        Returns: (annotated_frame, result)
        """
        try:
            # Detect faces
            faces = self.detect_faces(frame)
            
            if not faces:
                result = FaceDetectionResult(
                    detected=False,
                    recognized=False,
                    confidence=0.0,
                    bbox=(0, 0, 0, 0),
                    person_name="",
                    message="Không phát hiện khuôn mặt"
                )
                return frame, result
            
            # Lấy face lớn nhất (gần nhất)
            largest_face = max(faces, key=lambda f: f[2] * f[3])
            x, y, w, h = largest_face
            
            # Recognition
            name, confidence = self.recognize_face(frame, largest_face)
            is_recognized = name != "Unknown"
            
            # Vẽ annotations
            annotated_frame = self._draw_face_annotations(frame.copy(), largest_face, name, confidence, is_recognized)
            
            # Tạo result
            result = FaceDetectionResult(
                detected=True,
                recognized=is_recognized,
                confidence=confidence,
                bbox=largest_face,
                person_name=name if is_recognized else "",
                message=f"Nhận diện: {name}" if is_recognized else "Khuôn mặt chưa đăng ký"
            )
            
            return annotated_frame, result
            
        except Exception as e:
            logger.error(f"Lỗi process frame: {e}")
            result = FaceDetectionResult(
                detected=False,
                recognized=False,
                confidence=0.0,
                bbox=(0, 0, 0, 0),
                person_name="",
                message=f"Lỗi xử lý: {str(e)}"
            )
            return frame, result
    
    def _draw_face_annotations(self, frame: np.ndarray, bbox: Tuple[int, int, int, int], 
                             name: str, confidence: float, is_recognized: bool) -> np.ndarray:
        """Vẽ khung và text cho khuôn mặt"""
        x, y, w, h = bbox
        
        # Màu sắc
        color = (0, 255, 0) if is_recognized else (0, 0, 255)  # Green/Red
        
        # Vẽ khung chính
        thickness = 3
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, thickness)
        
        # Vẽ góc để làm đẹp
        corner_length = 25
        corner_thickness = 5
        
        # 4 góc
        corners = [
            [(x, y), (x + corner_length, y), (x, y + corner_length)],  # Top-left
            [(x + w, y), (x + w - corner_length, y), (x + w, y + corner_length)],  # Top-right  
            [(x, y + h), (x + corner_length, y + h), (x, y + h - corner_length)],  # Bottom-left
            [(x + w, y + h), (x + w - corner_length, y + h), (x + w, y + h - corner_length)]  # Bottom-right
        ]
        
        for corner in corners:
            cv2.line(frame, corner[0], corner[1], color, corner_thickness)
            cv2.line(frame, corner[0], corner[2], color, corner_thickness)
        
        # Text label
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.8
        text_thickness = 2
        
        # Label text
        if is_recognized:
            label_text = f"{name}"
            conf_text = f"({confidence:.1f})"
        else:
            label_text = "UNKNOWN"
            conf_text = ""
        
        # Kích thước text
        (text_w, text_h), _ = cv2.getTextSize(label_text, font, font_scale, text_thickness)
        
        # Background cho text
        text_bg_y = y - text_h - 15 if y - text_h - 15 > 0 else y + h + 5
        cv2.rectangle(frame, (x, text_bg_y), (x + text_w + 10, text_bg_y + text_h + 10), color, -1)
        
        # Vẽ text
        cv2.putText(frame, label_text, (x + 5, text_bg_y + text_h + 5), 
                   font, font_scale, (255, 255, 255), text_thickness)
        
        # Confidence text (nếu có)
        if conf_text:
            cv2.putText(frame, conf_text, (x, y + h + 25), 
                       font, 0.6, color, 2)
        
        # Status indicator
        status_color = (0, 255, 0) if is_recognized else (0, 0, 255)
        cv2.circle(frame, (x + w - 15, y + 15), 8, status_color, -1)
        cv2.circle(frame, (x + w - 15, y + 15), 8, (255, 255, 255), 2)
        
        return frame
    
    def add_person(self, name: str, face_images: List[np.ndarray]) -> bool:
        """Thêm người mới vào database"""
        try:
            if not face_images or not name:
                return False
            
            # Process face images
            processed_faces = []
            for img in face_images:
                # Convert to grayscale và resize
                if len(img.shape) == 3:
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                else:
                    gray = img
                
                gray = cv2.resize(gray, (100, 100))
                gray = cv2.equalizeHist(gray)  # Normalize lighting
                processed_faces.append(gray)
            
            # Thêm vào database
            self.known_faces_db[name] = {
                'faces': processed_faces,
                'added_time': time.time()
            }
            
            # Retrain recognizer
            self._train_recognizer()
            
            # Save database
            self._save_database()
            
            logger.info(f"✅ Đã thêm {name} với {len(face_images)} ảnh")
            return True
            
        except Exception as e:
            logger.error(f"❌ Lỗi thêm người: {e}")
            return False
    
    def _save_database(self):
        """Lưu database ra file"""
        try:
            db_file = os.path.join(self.face_data_path, "face_database.pkl")
            with open(db_file, 'wb') as f:
                pickle.dump(self.known_faces_db, f)
            logger.info("✅ Database đã được lưu")
        except Exception as e:
            logger.error(f"❌ Lỗi lưu database: {e}")
    
    def capture_training_images(self, frame: np.ndarray, variations: int = 1) -> List[np.ndarray]:
        """Capture training images từ frame"""
        try:
            faces = self.detect_faces(frame)
            if not faces:
                return []
            
            # Lấy face lớn nhất
            largest_face = max(faces, key=lambda f: f[2] * f[3])
            x, y, w, h = largest_face
            
            # Extract face ROI
            face_roi = frame[y:y+h, x:x+w]
            
            if face_roi.size == 0:
                return []
            
            # Tạo variations
            training_images = []
            
            for i in range(variations):
                variation = face_roi.copy()
                
                # Áp dụng augmentations nhẹ
                if i > 0:
                    # Random brightness
                    brightness = np.random.randint(-15, 16)
                    if brightness != 0:
                        variation = cv2.add(variation, np.ones(variation.shape, dtype=np.uint8) * brightness)
                    
                    # Random contrast
                    contrast = np.random.uniform(0.9, 1.1)
                    variation = cv2.multiply(variation, np.ones(variation.shape) * contrast)
                    
                    # Clip values
                    variation = np.clip(variation, 0, 255).astype(np.uint8)
                
                training_images.append(variation)
            
            return training_images
            
        except Exception as e:
            logger.error(f"Lỗi capture training images: {e}")
            return []
    
    def get_database_info(self) -> Dict:
        """Lấy thông tin database"""
        info = {
            'total_people': len(self.known_faces_db),
            'people': {}
        }
        
        for name, data in self.known_faces_db.items():
            info['people'][name] = {
                'face_count': len(data['faces']),
                'added_time': data.get('added_time', 0)
            }
        
        return info
    
    def remove_person(self, name: str) -> bool:
        """Xóa người khỏi database"""
        try:
            if name in self.known_faces_db:
                del self.known_faces_db[name]
                self._train_recognizer()
                self._save_database()
                logger.info(f"✅ Đã xóa {name} khỏi database")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Lỗi xóa người: {e}")
            return False
