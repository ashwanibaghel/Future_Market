import requests
import json

def create_sample_task():
    print("Creating a sample task via API...")
    url = "https://jsonplaceholder.typicode.com/todos"
    payload = {
        "title": "Sample Task created via API",
        "completed": False,
        "userId": 1
    }
    headers = {
        "Content-type": "application/json; charset=UTF-8"
    }
    
    try:
        response = requests.post(url, data=json.dumps(payload), headers=headers)
        response.raise_for_status()
        print("Task created successfully!")
        print("Response:", response.json())
    except requests.exceptions.RequestException as e:
        print(f"Failed to create task: {e}")

if __name__ == "__main__":
    create_sample_task()
