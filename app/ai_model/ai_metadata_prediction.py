import os
import json
import trimesh
import meshio
import requests
from stl import mesh as stlmesh
from duckduckgo_search import DDGS

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


# def web_enrich_prompt(filename):
#     try:
#         query = filename.replace('_', ' ').replace('-', ' ')
#         search_terms = f"{query} site:patreon.com OR site:myminifactory.com OR site:printables.com"
#         results = []
#         with DDGS() as ddgs:
#             for r in ddgs.text(search_terms, max_results=5):
#                 results.append(f"{r['title']}: {r['body']}")
#         return "\n".join(results)
#     except Exception as e:
#         return f"(Web enrichment failed: {str(e)})"
def web_enrich_prompt(filename):
    try:
        base = os.path.splitext(filename)[0]
        chunks = base.replace('-', ' ').replace('_', ' ').split()
        search_terms_list = [chunk for chunk in set(chunks) if len(chunk) > 2]
        if not search_terms_list:
            return ""
        query_terms = " ".join(search_terms_list)
        results = []
        sites = ["patreon.com", "myminifactory.com", "printables.com"]
        with DDGS() as ddgs:
            for site in sites:
                query = f"{query_terms} site:{site}"
                for i, r in enumerate(ddgs.text(query, max_results=2)):  # Limit to 2 results per site
                    title = r.get('title', '').strip()
                    body = r.get('body', '').strip().split('\n')[0]  # Only first line of body
                    if title or body:
                        results.append(f"{title}: {body}")
        # Limit total results to 5
        return "\n".join(results[:5])
    except Exception as e:
        return f"(Web enrichment failed: {str(e)})"


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
            "raw_response": response
        }

    except Exception as e:
        return {"error": f"LLM call failed: {str(e)}"}


def analyze_stl(filepath, enrich_with_web=True):
    metadata = extract_metadata(filepath)
    if "error" in metadata:
        return metadata

    web_context = web_enrich_prompt(metadata["filename"]) if enrich_with_web else ""
    prediction = call_local_llm(metadata, web_context=web_context)
    return prediction
