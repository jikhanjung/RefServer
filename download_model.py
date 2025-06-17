#!/usr/bin/env python3
"""
BGE-M3 모델 다운로드 스크립트
Docker 이미지에 포함시키기 위해 로컬에 모델을 미리 다운로드합니다.
"""

import os
import sys
from sentence_transformers import SentenceTransformer

def download_bge_m3_model():
    """BGE-M3 모델을 로컬에 다운로드"""
    
    model_name = "BAAI/bge-m3"
    local_model_path = "./models/bge-m3-local"
    
    print(f"Downloading BGE-M3 model: {model_name}")
    print("This may take several minutes depending on your internet connection...")
    
    try:
        # 모델 디렉토리 생성
        os.makedirs("./models", exist_ok=True)
        
        # 모델 다운로드
        print("Loading model from HuggingFace...")
        model = SentenceTransformer(model_name)
        
        # 로컬에 저장
        print(f"Saving model to {local_model_path}")
        model.save(local_model_path)
        
        print("✅ Model download completed successfully!")
        print(f"Model saved to: {os.path.abspath(local_model_path)}")
        
        # 모델 파일 크기 확인
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(local_model_path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                total_size += os.path.getsize(filepath)
        
        print(f"Total model size: {total_size / (1024*1024):.1f} MB")
        
        # 모델 파일 목록 출력
        print("\nModel files:")
        for root, dirs, files in os.walk(local_model_path):
            level = root.replace(local_model_path, '').count(os.sep)
            indent = ' ' * 2 * level
            print(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 2 * (level + 1)
            for file in files:
                print(f"{subindent}{file}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error downloading model: {e}")
        return False

def verify_model():
    """다운로드된 모델 검증"""
    local_model_path = "./models/bge-m3-local"
    
    if not os.path.exists(local_model_path):
        print("❌ Model directory not found")
        return False
    
    try:
        print("Verifying downloaded model...")
        
        # 모델 로드 테스트
        model = SentenceTransformer(local_model_path)
        
        # 간단한 임베딩 테스트
        test_text = "This is a test sentence for model verification."
        embedding = model.encode(test_text)
        
        print(f"✅ Model verification successful!")
        print(f"Embedding dimension: {len(embedding)}")
        print(f"Test embedding shape: {embedding.shape}")
        
        return True
        
    except Exception as e:
        print(f"❌ Model verification failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting BGE-M3 model download...")
    print("=" * 50)
    
    # 모델 다운로드
    success = download_bge_m3_model()
    
    if success:
        print("\n" + "=" * 50)
        print("🔍 Verifying downloaded model...")
        
        # 모델 검증
        verify_success = verify_model()
        
        if verify_success:
            print("\n" + "=" * 50)
            print("🎉 All done! Model is ready for Docker deployment.")
            print("\nNext steps:")
            print("1. Build Docker image with: docker-compose build")
            print("2. The model will be available at /app/models/bge-m3-local inside the container")
        else:
            print("\n❌ Model verification failed. Please try downloading again.")
            sys.exit(1)
    else:
        print("\n❌ Model download failed. Please check your internet connection and try again.")
        sys.exit(1)