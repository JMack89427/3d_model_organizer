import os
import json
import requests
from stl import mesh
from duckduckgo_search import DDGS


def extract_stl_metadata(filepath):
    try:
        model = mesh.Mesh.from_file(filepath)
        num_triangles = len(model)
        min_ = model.min_.tolist()
        max_ = model.max_.tolist()
        volume = model.get_mass_properties()[0]

        return {
            "num_triangles": num_triangles,
            "bounding_box_min": min_,
            "bounding_box_max": max_,
            "volume": volume,
            "filename": os.path.basename(filepath)
        }
    except Exception as e:
        return {"error": f"Failed to parse STL: {str(e)}"}


def web_enrich_prompt(filename):
    try:
        # Break down filename into searchable chunks (remove extension, split on delimiters)
        base = os.path.splitext(filename)[0]
        chunks = base.replace('-', ' ').replace('_', ' ').split()
        # Use unique, non-trivial chunks (length > 2)
        search_terms_list = [chunk for chunk in set(chunks) if len(chunk) > 2]
        creators = set()
        sites = ["patreon.com", "myminifactory.com", "printables.com"]
        with DDGS() as ddgs:
            for chunk in search_terms_list:
                for site in sites:
                    query = f"{chunk} site:{site}"
                    for r in ddgs.text(query, max_results=5):
                        # Filter out Thingiverse results
                        if "thingiverse" in r.get('title', '').lower() or "thingiverse" in r.get('body', '').lower():
                            continue
                        # Try to extract creator names from title/body
                        for text in [r.get('title', ''), r.get('body', '')]:
                            lowered = text.lower()
                            if "by " in lowered:
                                # e.g. "Model Name by John Doe"
                                parts = lowered.split("by ")
                                if len(parts) > 1:
                                    possible = parts[1].split()[0:3]
                                    creators.add(" ".join(possible).title())
                            elif "creator:" in lowered:
                                # e.g. "creator: John Doe"
                                parts = lowered.split("creator:")
                                if len(parts) > 1:
                                    possible = parts[1].split()[0:3]
                                    creators.add(" ".join(possible).title())
        return list(creators)
    except Exception as e:
        return [f"(Web enrichment failed: {str(e)})"]


def call_local_llm(metadata_dict, filepath):
    web_context = web_enrich_prompt(filepath)
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
        response = requests.post(
            "http://host.docker.internal:11434/api/generate",
            json={
                "model": "llama3",
                "prompt": prompt,
                "stream": False
            },
            timeout=60
        )
        response.raise_for_status()
        result_json = response.json()
        output = result_json.get("response", "")

        # Try to extract JSON from output
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


def analyze_stl(filepath):
    metadata = extract_stl_metadata(filepath)
    if "error" in metadata:
        return metadata

    result = call_local_llm(metadata, filepath)
    if "error" in result:
        return result

    # Merge metadata and LLM results for convenience
    return {
        **result["llm_response"],
        "web_context": result["web_context"],
        "prompt": result["prompt"],
        "raw_response": result["raw_response"]
    }