import json

with open('example.txt', 'r') as file:
    try:
        contents = file.read()
        data = json.loads(contents)
    except ValueError:
        print("File is empty, initializing data")
        data = {'counter': 0}
    print(data)
    counter = data.get('counter', 0)
    counter = counter + 1
    data['counter'] = counter

with open('example.txt', 'w') as file:
    file.seek(0)
    json.dump(data, file)
