import os
import json
import requests
from stl import mesh


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
        }
    except Exception as e:
        return {"error": f"Failed to parse STL: {str(e)}"}


def call_local_llm(metadata_dict, filename):
    prompt = f"""
    Given the following metadata from an STL file named "{filename}":

    {json.dumps(metadata_dict, indent=2)}

    Predict:
    - Creator (who likely made this file)
    - Likely original filename (before upload)
    - File type (e.g., STL, OBJ, 3MF)

    Return a JSON object with keys: creator, filename, filetype.
    """

    try:
        response = requests.post(
            "http://host.docker.internal:11434/api/generate",
            json={
                "model": "mistral",
                "prompt": prompt,
                "stream": False
            },
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        # Ollama returns the output in the 'response' field
        output = result.get("response", "")

        # Try to extract JSON from output
        start = output.find('{')
        end = output.rfind('}') + 1
        json_str = output[start:end]
        return json.loads(json_str)

    except Exception as e:
        return {"error": f"LLM call failed: {str(e)}"}


def analyze_stl(filepath):
    metadata = extract_stl_metadata(filepath)
    if "error" in metadata:
        return metadata

    filename = os.path.basename(filepath)
    prediction = call_local_llm(metadata, filename)
    return prediction


if __name__ == "__main__":
    test_path = "test_files/example.stl"
    result = analyze_stl(test_path)
    print(json.dumps(result, indent=2))
