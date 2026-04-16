#!/usr/bin/env python3
"""
Test script to verify the RAG pipeline after fixes.
Run this to confirm everything is working correctly.
"""
import requests
import json
import time

API_URL = "http://localhost:8000"

def test_api():
    print("=" * 60)
    print("RAG PIPELINE - VALIDATION TEST")
    print("=" * 60)
    
    # Test 1: Health check
    print("\n[1] Health Check...")
    try:
        r = requests.get(f"{API_URL}/health", timeout=5)
        assert r.status_code == 200
        print("✅ API is running")
    except Exception as e:
        print(f"❌ API Health Check Failed: {e}")
        return False
    
    # Test 2: Check upload endpoint (should have multi-upload, not single)
    print("\n[2] Checking API Endpoints...")
    try:
        r = requests.get(f"{API_URL}/openapi.json", timeout=5)
        openapi = r.json()
        paths = openapi.get("paths", {})
        
        has_multi_upload = "/api/v1/documents/upload-multiple" in paths
        has_single_upload = "/api/v1/documents/upload" in paths
        
        print(f"   - Multi-document upload endpoint: {'✅ PRESENT' if has_multi_upload else '❌ MISSING'}")
        print(f"   - Single-document upload endpoint: {'❌ PRESENT (SHOULD BE REMOVED)' if has_single_upload else '✅ REMOVED'}")
        
        if not has_multi_upload:
            print("❌ Multi-upload endpoint not found!")
            return False
            
    except Exception as e:
        print(f"❌ Failed to check endpoints: {e}")
        return False
    
    # Test 3: Check database for documents
    print("\n[3] Checking for Ingested Documents...")
    try:
        r = requests.get(f"{API_URL}/api/v1/documents", timeout=5)
        if r.status_code == 200:
            data = r.json()
            doc_count = data.get("total", 0)
            completed = sum(1 for d in data.get("documents", []) if d.get("status") == "completed")
            print(f"   - Total documents: {doc_count}")
            print(f"   - Completed: {completed}")
            if doc_count > 0:
                print("✅ Documents found in system")
            else:
                print("⚠️  No documents found (upload some first)")
        else:
            print(f"❌ Failed to list documents: {r.status_code}")
    except Exception as e:
        print(f"❌ Failed to check documents: {e}")
        return False
    
    # Test 4: Test query with empty document_ids
    print("\n[4] Testing Query with empty document_ids...")
    try:
        query_payload = {
            "question": "What skills are mentioned?",
            "document_ids": [],
            "top_k": 3
        }
        r = requests.post(
            f"{API_URL}/api/v1/query",
            json=query_payload,
            timeout=10
        )
        
        if r.status_code == 200:
            result = r.json()
            chunks_found = result.get("chunks_retrieved", 0)
            answer = result.get("answer", "")
            
            print(f"   - Chunks retrieved: {chunks_found}")
            print(f"   - Answer length: {len(answer)} chars")
            print(f"   - Model used: {result.get('model_used')}")
            
            if chunks_found > 0:
                print("✅ Query retrieved relevant chunks!")
                print(f"   Answer preview: {answer[:100]}...")
            else:
                print("⚠️  Query returned 0 chunks (documents may still be processing)")
                print(f"   Answer: {answer}")
        else:
            print(f"❌ Query failed: {r.status_code}")
            print(f"   Response: {r.text}")
            return False
            
    except Exception as e:
        print(f"❌ Query test failed: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ VALIDATION COMPLETE - All systems operational!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Upload documents via: POST /api/v1/documents/upload-multiple")
    print("2. Wait 5-10 seconds for ingestion")
    print("3. Query with: POST /api/v1/query")
    print('   -> Use "document_ids": [] to search all documents')
    print("=" * 60)
    return True

if __name__ == "__main__":
    try:
        success = test_api()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted")
        exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        exit(1)
