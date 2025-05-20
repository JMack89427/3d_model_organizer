
import os
import json
import subprocess
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
        query = filename.replace('_', ' ').replace('-', ' ')
        search_terms = f"{query} site:patreon.com OR site:thingiverse.com OR site:printables.com"
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(search_terms, max_results=5):
                results.append(f"{r['title']}: {r['body']}")
        return "\n".join(results)
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
        result = subprocess.run(
            ["ollama", "run", "llama3"],
            input=prompt.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30
        )

        if result.returncode != 0:
            return {"error": result.stderr.decode("utf-8")}

        response = result.stdout.decode("utf-8")

        # Try to extract JSON from response
        start = response.find('{')
        end = response.rfind('}') + 1
        json_str = response[start:end]
        return json.loads(json_str)

    except Exception as e:
        return {"error": f"LLM call failed: {str(e)}"}


def analyze_stl(filepath, enrich_with_web=True):
    metadata = extract_stl_metadata(filepath)
    if "error" in metadata:
        return metadata

    web_context = web_enrich_prompt(metadata["filename"]) if enrich_with_web else ""
    prediction = call_local_llm(metadata, web_context=web_context)
    return prediction
