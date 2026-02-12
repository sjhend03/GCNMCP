import requests
import json
from typing import List, Dict, Any
import re

import pandas as pd

class MCPClient:
    def __init__(self, server_url="http://localhost:8080/mcp"):
        self.server_url = server_url
        self.request_id = 0

    def _call(self, method, params=None):
        self.request_id += 1
        payload = {
            'jsonrpc': "2.0",
            'method': method,
            'params': params or {},
            'id': self.request_id,
        }
        response = requests.post(self.server_url, json=payload)
        return response.json()
    
    def call_tool(self, tool_name, arguments):
        return self._call('tools/call', {
            'name': tool_name,
            'arguments': arguments,
        })
    
if __name__ == '__main__':
    client = MCPClient()
    
    print("Loading file list...")
    paths_res = client.call_tool('fetch_gcn_circular_name_local', {'data_dir_name': 'data'})
    print(paths_res["result"][0])

    test_file_path = paths_res["result"][0]

    test_file_res = client.call_tool("load_gcn_circular", {"path": test_file_path})
    test_file = test_file_res["result"][0]
    #test_file = json.loads(test_file)
    #print(test_file)
    test_file_body = json.loads(test_file["text"])["body"]
    test_file_subject = json.loads(test_file["text"])["subject"]
    #print(test_file_body)
    #print(test_file_subject)

    paths_res = client.call_tool('fetch_gcn_circular_name_local', {'data_dir_name': 'data'})
    paths = paths_res["result"]
    paths = sorted(paths, key=lambda x: int(re.search(r'\d+', x).group()))
    print(f"Amount of circular: {len(paths)}")

    # Function to help parse the swift redshifts
    def get_z(text):
        match = re.search(r'(\d+\.?\d*)', str(text))
        return float(match.group(1)) if match else None
    
    # GRB redshift search
    swift_table = pd.read_csv("swift_table.txt", sep="\t")
    print(swift_table.keys())
    
    # Apply get_z to extract numeric redshifts
    swift_table['z_numeric'] = swift_table["Redshift"].apply(get_z)
    grb_dict = dict(zip(swift_table['GRB'], swift_table['z_numeric']))

    start_file = 6000
    end_file = len(paths)  # Check all files
    results = []

    paths_res = client.call_tool('fetch_gcn_circular_name_local', {'data_dir_name': 'data'})
    paths = paths_res["result"]
    paths = sorted(paths, key=lambda x: int(re.search(r'\d+', x).group()))
    print(f"Amount of circular: {len(paths)}")

    accurate = []
    matched_count = 0  # Track how many are in Swift table
    mismatches = []

    for i in range(end_file - start_file):
        print(f"result from file: {i + start_file} with path: {paths[start_file + i]}")
        file = client.call_tool("load_gcn_circular", {"path": paths[start_file + i]})
        file = file["result"][0]
        
        # Extract event ID to check against Swift table
        circular = json.loads(file["text"])
        event_id = circular.get("eventId", "").replace("GRB ", "").strip()
        
        file_subject = circular["subject"]
        file_body = circular["body"]

        # Check if this GRB is in Swift table
        if event_id in grb_dict:
            matched_count += 1
            print(f"  ✓ {event_id} found in Swift table (z={grb_dict[event_id]})")
            
            relevant_file_content = {"subject": file_subject, "body": file_body}

            grb_analysis = client.call_tool("check_for_grb_redshift", {"content": relevant_file_content})
            print(grb_analysis)
            results.append(grb_analysis)
            grb_analysis = grb_analysis["result"]

            if grb_analysis["has_redshift"] == True:
                try:
                    llm_z = float(grb_analysis["z"])
                    actual_z = grb_dict[event_id]
                    if abs(llm_z - actual_z) < 0.05:
                        accurate.append(True)
                    else:
                        accurate.append(False)
                        print(f"  Mismatch: LLM={llm_z}, Swift={actual_z}")
                        mismatches.append({
                            "llm_z": llm_z,
                            "actual_z": actual_z,
                            "event_id": event_id,
                            "relevent_file_content": relevant_file_content,
                        })
                except (ValueError, TypeError):
                    print(f"  Invalid value for {event_id}: {grb_analysis['z']}")
            else:
                print(f"  Missed redshift for {event_id}")
        else:
            print(f"  - {event_id} not in Swift table, skipping")   

        if len(accurate) > 100:
            break

    print(f"\n=== SUMMARY ===")
    print(f"Files checked: {end_file - start_file}")
    print(f"Matched in Swift table: {matched_count}")
    if accurate:
        percentage = (accurate.count(True) / len(accurate)) * 100
        print(f"Accuracy: {percentage:.2f}%")
    else:
        print("No matches found to validate")

    with open("accurate.txt", "w", encoding="utf-8") as f:
        print(accurate, file=f)

    with open("mismatches.txt", "w", encoding="utf-8") as f:
        print(mismatches, file=f)

            