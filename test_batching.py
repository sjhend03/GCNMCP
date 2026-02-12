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
    paths = paths_res["result"]
    paths = sorted(paths, key=lambda x: int(re.search(r'\d+', x).group()))
    print(f"Amount of circular: {len(paths)}")

    # Function to help parse the swift redshifts
    def get_z(text):
        match = re.search(r'(\d+\.?\d*)', str(text))
        return float(match.group(1)) if match else None
    
    # GRB redshift search
    swift_table = pd.read_csv("swift_table.txt", sep="\t")
    swift_table['z_numeric'] = swift_table["Redshift"].apply(get_z)
    grb_dict = dict(zip(swift_table['GRB'], swift_table['z_numeric']))
    swift_grbs = set(swift_table['GRB'])

    start_file = 0
    end_file = len(paths)
    BATCH_SIZE = 10  # Number of circulars per batch
    
    accurate = []
    matched_count = 0
    mismatches = []
    results = []

    # Collect all Swift-matched circulars first
    swift_circulars = []
    event_id_list = []
    body_list = []
    
    for i in range(end_file - start_file):
        print(f"Scanning file: {i + start_file}")
        file = client.call_tool("load_gcn_circular", {"path": paths[start_file + i]})
        file = file["result"][0]
        
        circular = json.loads(file["text"])
        event_id = circular.get("eventId", "").replace("GRB ", "").strip()
        
        if event_id in swift_grbs:
            swift_circulars.append({
                'event_id': event_id,
                'subject': circular["subject"],
                'body': circular["body"],
                'actual_z': grb_dict[event_id]
            })
            matched_count += 1
            print(f"  ✓ {event_id} found in Swift table")
        
        if matched_count >= 100:  # Stop after finding 100 Swift matches
            break

    print(f"\nFound {matched_count} Swift-matched circulars, processing in batches...")

    # Process in batches
    for batch_start in range(0, len(swift_circulars), BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, len(swift_circulars))
        batch = swift_circulars[batch_start:batch_end]
        
        print(f"\nProcessing batch {batch_start//BATCH_SIZE + 1} ({len(batch)} circulars)...")
        
        # Create batch content with masked IDs
        batch_text = ""
        masked_mapping = {}
        
        for idx, circ in enumerate(batch):
            masked_id = f"GRB_{batch_start + idx}"
            masked_mapping[masked_id] = circ
            batch_text += f"\n---CIRCULAR {masked_id}---\n"
            batch_text += f"Subject: {circ['subject']}\n\n"
            batch_text += f"{circ['body']}\n"
        
        # Single LLM call for entire batch
        grb_analysis = client.call_tool("check_for_grb_redshift_batch", {
            "content": batch_text,
            "circular_ids": list(masked_mapping.keys())
        })
        
        results.append(grb_analysis)
        batch_results = grb_analysis["result"]
        
        # Process batch results
        for masked_id, result in batch_results.items():
            circ = masked_mapping[masked_id]
            event_id = circ['event_id']
            actual_z = circ['actual_z']
            
            if result["has_redshift"] == True:
                try:
                    llm_z = float(result["z"])
                    if abs(llm_z - actual_z) < 0.05:
                        accurate.append(True)
                        print(f"  ✓ {event_id}: LLM={llm_z:.3f}, Swift={actual_z:.3f}")
                    else:
                        accurate.append(False)
                        print(f"  ✗ {event_id}: LLM={llm_z:.3f}, Swift={actual_z:.3f}")
                        mismatches.append({
                            "llm_z": llm_z,
                            "actual_z": actual_z,
                            "event_id": event_id,
                            "subject": circ['subject'],
                            "body": circ['body']
                        })
                except (ValueError, TypeError):
                    accurate.append(False)
                    print(f"  ✗ {event_id}: Invalid value {result['z']}")
            else:
                accurate.append(False)
                print(f"  ✗ {event_id}: Missed redshift")

    print(f"\n=== SUMMARY ===")
    print(f"Files scanned: {i + 1}")
    print(f"Matched in Swift table: {matched_count}")
    print(f"Total LLM calls: {len(range(0, len(swift_circulars), BATCH_SIZE))}")
    if accurate:
        percentage = (accurate.count(True) / len(accurate)) * 100
        print(f"Accuracy: {percentage:.2f}%")
    else:
        print("No matches found to validate")

    # Save to different files
    with open("accurate_batch.txt", "w", encoding="utf-8") as f:
        print(accurate, file=f)

    with open("mismatches_batch.json", "w", encoding="utf-8") as f:
        json.dump(mismatches, f, indent=2)
    
    with open("results_batch.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)