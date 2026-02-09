import requests
import json
from typing import List, Dict, Any

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
    print(test_file)
    test_file_body = json.loads(test_file["text"])["body"]
    test_file_subject = json.loads(test_file["text"])["subject"]
    print(test_file_body)
    print(test_file_subject)

    # GRB redshift search
    start_file = 0
    end_file = 10
    red_shifts = []
    paths_res = client.call_tool('fetch_gcn_circular_name_local', {'data_dir_name': 'data'})
    paths = paths_res["result"]

    for i in range(end_file - start_file):
        file = client.call_tool("load_gcn_circular", {"path": paths[start_file + i]})
        file = file["result"][0]
        file_subject = json.loads(file["text"])["subject"]
        file_body = json.loads(file["text"])["body"]

        relevant_file_content = {"subject": file_subject, "body": file_body}

        grb_analysis = client.call_tool("check_for_grb_redshift", {"content": relevant_file_content})
        print(grb_analysis)
