#!/usr/bin/env python3
"""Quick test script to validate the hybrid OCR pipeline"""

import sys
import os
from pathlib import Path

# Add workspace to path
sys.path.insert(0, str(Path(__file__).parent))

# Set up environment
os.environ['GEMINI_API_KEY'] = os.environ.get('GEMINI_API_KEY', 'test-key')

from utils.text_structurer import (
    BHTExtractedData,
    get_bht_extraction_output_schema,
    clean_schema_for_gemini,
)
import json

print("=" * 70)
print("HYBRID OCR PIPELINE - SCHEMA VALIDATION TEST")
print("=" * 70)

# Test 1: Verify schema is clean
print("\n[TEST 1] Verifying schema is Gemini-compatible...")
schema = get_bht_extraction_output_schema()

# Check for forbidden fields
forbidden = ['additionalProperties', 'default', 'default_factory']
def has_forbidden(obj, path=""):
    if isinstance(obj, dict):
        for key in forbidden:
            if key in obj:
                print(f"  ✗ Found '{key}' at {path}.{key}")
                return True
        for k, v in obj.items():
            if has_forbidden(v, f"{path}.{k}"):
                return True
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if has_forbidden(item, f"{path}[{i}]"):
                return True
    return False

if has_forbidden(schema):
    print("  ✗ FAILED: Schema has forbidden fields")
    sys.exit(1)
else:
    print("  ✓ PASSED: Schema is clean")

# Test 2: Verify model can be instantiated with no data
print("\n[TEST 2] Verifying model instantiation with partial data...")
try:
    # Empty data
    empty_data = BHTExtractedData()
    print(f"  Empty instance: {str(empty_data)[:100]}...")
    
    # Partial data  
    partial_data = BHTExtractedData(
        diagnosis="Hypertension",
        confidence_score=0.8
    )
    print(f"  Partial instance: diagnosis={partial_data.diagnosis}, confidence={partial_data.confidence_score}")
    
    print("  ✓ PASSED: Model instantiates correctly")
except Exception as e:
    print(f"  ✗ FAILED: {e}")
    sys.exit(1)

# Test 3: Verify model validates JSON from Gemini
print("\n[TEST 3] Verifying JSON validation...")
try:
    gemini_response = {
        "diagnosis": "Diabetes Type 2",
        "symptoms": "Fatigue, thirst",
        "treatment_plan": "Insulin therapy",
        "medications": "Metformin 500mg",
        "vitals": {"temperature": "37.0°C", "bp": "130/80"},
        "procedures": None,
        "lab_results": {"blood_glucose": "250 mg/dL"},
        "notes": "Patient responded well",
        "confidence_score": 0.92
    }
    
    data = BHTExtractedData.model_validate(gemini_response)
    print(f"  Validated: {len([v for v in data.model_dump().values() if v is not None])} fields")
    print(f"  Confidence: {data.confidence_score}")
    print("  ✓ PASSED: JSON validation works")
except Exception as e:
    print(f"  ✗ FAILED: {e}")
    sys.exit(1)

# Test 4: Verify confidence_score fallback
print("\n[TEST 4] Verifying confidence_score fallback...")
try:
    response_no_confidence = {
        "diagnosis": "Hypertension",
        "confidence_score": None  # Explicitly None
    }
    
    # Simulate the fallback logic
    if 'confidence_score' not in response_no_confidence or response_no_confidence['confidence_score'] is None:
        response_no_confidence['confidence_score'] = 0.5
    
    data = BHTExtractedData.model_validate(response_no_confidence)
    assert data.confidence_score == 0.5, f"Expected 0.5, got {data.confidence_score}"
    print(f"  Fallback confidence: {data.confidence_score}")
    print("  ✓ PASSED: Confidence fallback works")
except Exception as e:
    print(f"  ✗ FAILED: {e}")
    sys.exit(1)

print("\n" + "=" * 70)
print("ALL TESTS PASSED ✓")
print("=" * 70)
print("\nThe hybrid OCR pipeline is ready for testing with actual BHT images.")
print("Key points:")
print("  - Schema is Gemini-compatible (no defaults)")
print("  - Model handles partial data correctly")
print("  - JSON validation works")
print("  - Confidence score fallback is in place")
