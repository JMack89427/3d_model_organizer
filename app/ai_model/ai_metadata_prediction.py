import os
import json
import trimesh
import meshio
import requests
from stl import mesh as stlmesh
from dotenv import load_dotenv

load_dotenv()  # Ensure .env variables are loaded before using os.getenv

API_KEY = os.getenv("VERTEX_API_KEY")
APP_ID = os.getenv("VERTEX_SEARCH_APP_ID")
DATASTORE_ID = os.getenv("VERTEX_DATASTORE_ID")

SUPPORTED_EXTENSIONS = {'.stl', '.obj', '.3mf', '.step', '.stp'}


def extract_metadata(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == '.stl':
            model = stlmesh.Mesh.from_file(filepath)
            num_triangles = len(model)
            min_ = model.min_.tolist()
            max_ = model.max_.tolist()
            volume = model.get_mass_properties()[0]
        elif ext == '.obj':
            model = trimesh.load(filepath, force='mesh')
            num_triangles = len(model.faces)
            min_, max_ = model.bounds
            volume = model.volume
        elif ext == '.3mf':
            model = meshio.read(filepath)
            num_triangles = len(model.cells_dict.get('triangle', []))
            volume = None  # Optional, depending on mesh quality
            min_, max_ = [0, 0, 0], [0, 0, 0]
        elif ext in {'.step', '.stp'}:
            return {"error": "STEP file parsing not implemented in this build."}
        else:
            return {"error": f"Unsupported file format: {ext}"}
    except Exception as e:
        return {"error": f"Failed to parse {ext} file: {str(e)}"}

    return {
        "file_extension": ext,
        "num_triangles": num_triangles,
        "bounding_box_min": min_,
        "bounding_box_max": max_,
        "volume": volume,
        "filename": os.path.basename(filepath)
    }

def web_enrich_prompt(filename):
    if not API_KEY or not APP_ID or not DATASTORE_ID:
        return "(Vertex AI config missing)"

    query = filename.replace('_', ' ').replace('-', ' ')
    # url = f"https://discoveryengine.googleapis.com/v1alpha/{APP_ID}/servingConfigs/default_search:search"
    url = (
    "https://discoveryengine.googleapis.com/v1alpha/"
    f"projects/{APP_ID}/locations/global/collections/default_collection/"
    f"dataStores/{DATASTORE_ID}/servingConfigs/default_search:search"
    )

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": API_KEY,
    }

    data = {
        "query": query,
        "pageSize": 5,
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        results = response.json().get("results", [])
        return "\n".join(r["document"]["derivedStructData"]["snippet"] for r in results if "document" in r)
    except Exception as e:
        return f"(Vertex search failed: {str(e)})"

def call_local_llm(metadata_dict, web_context=""):
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
        # Use HTTP API instead of subprocess
        response = requests.post(
            "http://localhost:11434/api/generate",  # Local Ollama endpoint
            json={
                "model": "llama3",
                "prompt": prompt,
                "stream": False
            },
            timeout=30
        )
        response.raise_for_status()  # Raise exception for HTTP errors
        
        # Get the actual text content from the response
        result = response.json()
        output = result.get("response", "")
        
        # Try to extract JSON from response
        start = output.find('{')
        end = output.rfind('}') + 1
        json_str = output[start:end]
        llm_response = json.loads(json_str)
        return {
            "llm_response": llm_response,
            "web_context": web_context,
            "prompt": prompt,
            "raw_response": output
        }

    except Exception as e:
        return {"error": f"LLM call failed: {str(e)}"}


def analyze_stl(filepath, enrich_with_web=True):
    metadata = extract_metadata(filepath)
    if "error" in metadata:
        return metadata

    web_context = web_enrich_prompt(metadata["filename"]) if enrich_with_web else ""
    result = call_local_llm(metadata, web_context=web_context)
    if "error" in result:
        return result
        
    # Merge LLM response and context fields
    return {
        **result["llm_response"],
        "web_context": result["web_context"],
        "prompt": result["prompt"],
        "raw_response": result["raw_response"]
    }
