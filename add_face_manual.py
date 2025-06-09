#!/usr/bin/env python3
"""
Script thêm khuôn mặt thủ công vào AI database
"""

import cv2
import os
import time
import numpy as np
from improved_face_recognition import ImprovedFaceRecognition

def add_face_manual():
    print("🤖 THÊM KHUÔN MẶT VÀO AI DATABASE")
    print("=" * 50)
    
    # Khởi tạo face recognizer
    face_recognizer = ImprovedFaceRecognition(
        models_path="/home/khoi/Desktop/KHOI_LUANAN/models",
        face_data_path="/home/khoi/Desktop/KHOI_LUANAN/face_data"
    )
    
    # Nhập tên
    name = input("👤 Nhập tên của bạn: ").strip()
    if not name:
        print("❌ Tên không được để trống!")
        return
    
    print(f"📸 Sẽ chụp 25 ảnh training cho: {name}")
    print("👁️ Hướng dẫn:")
    print("   - Nhìn thẳng vào camera")
    print("   - Di chuyển đầu nhẹ (trái, phải, lên, xuống)")
    print("   - Đảm bảo ánh sáng tốt")
    print("   - Bấm SPACE để chụp, ESC để thoát")
    print()
    
    # Khởi tạo camera
    try:
        from picamera2 import Picamera2
        camera = Picamera2()
        camera.configure(camera.create_video_configuration(
            main={"format": 'XRGB8888', "size": (800, 600)}
        ))
        camera.start()
        time.sleep(2)
        print("✅ Camera sẵn sàng!")
    except:
        print("❌ Không thể khởi tạo camera!")
        return
    
    captured_images = []
    target_images = 25
    
    try:
        while len(captured_images) < target_images:
            # Capture frame
            frame = camera.capture_array()
            if frame is None:
                continue
            
            # Hiển thị frame
            display_frame = cv2.resize(frame, (640, 480))
            cv2.putText(display_frame, f"Training: {name}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(display_frame, f"Images: {len(captured_images)}/{target_images}", (10, 70), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.putText(display_frame, "SPACE: Capture | ESC: Exit", (10, 450), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            
            # Detect faces để hiển thị khung
            faces = face_recognizer.detect_faces(frame)
            for (x, y, w, h) in faces:
                # Scale coordinates for display
                scale_x = 640 / 800
                scale_y = 480 / 600
                x_scaled = int(x * scale_x)
                y_scaled = int(y * scale_y)
                w_scaled = int(w * scale_x)
                h_scaled = int(h * scale_y)
                
                cv2.rectangle(display_frame, (x_scaled, y_scaled), 
                             (x_scaled + w_scaled, y_scaled + h_scaled), (0, 255, 0), 2)
                cv2.putText(display_frame, "Face Detected", (x_scaled, y_scaled-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            cv2.imshow('AI Face Training', display_frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord(' '):  # Space to capture
                if faces:
                    # Capture training image
                    training_images = face_recognizer.capture_training_images(frame, 1)
                    if training_images:
                        captured_images.extend(training_images)
                        print(f"📸 Captured image {len(captured_images)}/{target_images}")
                        
                        # Visual feedback
                        cv2.rectangle(display_frame, (0, 0), (640, 480), (0, 255, 0), 5)
                        cv2.imshow('AI Face Training', display_frame)
                        cv2.waitKey(200)  # Flash effect
                    else:
                        print("❌ Không phát hiện khuôn mặt rõ ràng!")
                else:
                    print("❌ Không có khuôn mặt trong khung hình!")
                    
            elif key == 27:  # ESC to exit
                print("🔄 Thoát training...")
                break
                
            time.sleep(0.1)
        
        cv2.destroyAllWindows()
        camera.stop()
        
        if len(captured_images) >= 15:
            print(f"\n🧠 Đang xử lý {len(captured_images)} ảnh training...")
            
            if face_recognizer.add_person(name, captured_images):
                print("✅ TRAINING THÀNH CÔNG!")
                print(f"👤 Đã thêm {name} vào AI database")
                print(f"📸 Với {len(captured_images)} ảnh training")
                
                # Hiển thị thống kê
                info = face_recognizer.get_database_info()
                print(f"\n📊 THỐNG KÊ DATABASE:")
                print(f"   👥 Tổng số người: {info['total_people']}")
                print(f"   📸 Tổng ảnh: {sum(p['face_count'] for p in info['people'].values())}")
                return True
            else:
                print("❌ Lỗi lưu dữ liệu training!")
        else:
            print(f"❌ Không đủ ảnh training! Cần ít nhất 15 ảnh, có {len(captured_images)}")
            
    except Exception as e:
        print(f"❌ Lỗi training: {e}")
    finally:
        cv2.destroyAllWindows()
        if 'camera' in locals():
            camera.stop()
    
    return False

if __name__ == "__main__":
    add_face_manual()
