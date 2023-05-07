
#import aioredis
import quart
import quart_cors
from quart import request, jsonify, send_from_directory
from quart_redis import RedisHandler, get_redis
import os
import subprocess

memories = {}

app = quart_cors.cors(quart.Quart(__name__), allow_origin="https://chat.openai.com")
app.config['REDIS_URI'] = 'redis://localhost:6379/0'
r = RedisHandler(app)

@app.route('/pub/<path:filename>')
async def serve_static_file(filename):
    static_folder = './pub'
    return await send_from_directory(static_folder, filename, conditional=True)

@app.route('/memories', methods=['POST'])
async def create_memory():
    if request.content_type != 'application/json':
        return jsonify({'error': 'Only application/json content type is supported'}), 415
    data = await request.get_json()
    memory_id = data.get('id')
    text = data.get('text')
    if not memory_id or not text:
        return jsonify({'error': 'Both "id" and "text" fields are required'}), 400
    redis = get_redis()
    if await redis.exists(memory_id):
        return jsonify({'error': 'Memory with this id already exists'}), 409
    await redis.set(memory_id, text)
    return jsonify({'id': memory_id}), 201

@app.route('/memories', methods=['GET'])
async def list_memories():
    redis = get_redis()
    keys = await redis.keys('*')
    keys_str = [key.decode('utf-8') for key in keys]
    return jsonify(keys_str), 200

@app.route('/memories/<memory_id>', methods=['GET'])
async def get_memory(memory_id):
    redis = get_redis()
    memory = await redis.get(memory_id)
    if not memory:
        return jsonify({'error': 'Memory not found'}), 404
    return jsonify({'id': memory_id, 'text': memory.decode('utf-8')}), 200

def create_virtual_environment():
    venv_path = './venv'
    os.makedirs(venv_path, exist_ok=True)
    subprocess.run(['python3', '-m', 'venv', venv_path])

def run_python(code):
    create_virtual_environment()
    venv_python = os.path.join('venv', 'bin', 'python')

    # Write the code to a temporary main.py file
    with open('main.py', 'w') as f:
        f.write(code)

    # Use the virtual environment Python interpreter to execute the main.py file
    process = subprocess.run([venv_python, 'main.py'], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    exit_code = process.returncode
    stdout = process.stdout.strip()
    stderr = process.stderr.strip()

    # Remove the main.py file after execution
    os.remove('main.py')

    return exit_code, stdout, stderr if not 'Debugger warning:' in stderr else ''

def run_bash(code):
    # If the virtual environment does not exist, create it
    create_virtual_environment()

    # Set up the virtual environment by sourcing the activate script
    venv_activate = os.path.join('venv', 'bin', 'activate')
    code_with_venv = f'source {venv_activate}; {code}'

    process = subprocess.run(code_with_venv, shell=True, executable='/bin/bash', text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    exit_code = process.returncode
    stdout = process.stdout.strip()
    stderr = process.stderr.strip()

    return exit_code, stdout, stderr

def run_applescript(code):
    command = f"osascript -e '{code}'"
    process = subprocess.run(command, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    exit_code = process.returncode
    stdout = process.stdout.strip()
    stderr = process.stderr.strip()

    return exit_code, stdout, stderr

@app.route('/run_script', methods=['POST'])
async def run_script():
    content_type = request.headers.get("Content-Type")
    
    if not content_type or content_type != 'application/json':
        return jsonify({'error': 'Only application/json content type is supported'}), 415

    try:
        data = await request.get_json()
    except Exception as e:
        return jsonify({'error': f'Parsing error: {str(e)}'}), 400

    language = data.get('language')
    code = data.get('code')

    if not language or not code:
        return jsonify({'error': 'Both "language" and "code" fields are required'}), 400

    initial_cwd = os.getcwd()
    os.chdir('./dwd')
    try:
        if language == "python":
            exit_code, stdout, stderr = run_python(code)
        elif language == "bash":
            exit_code, stdout, stderr = run_bash(code)
        elif language == "applescript":
            exit_code, stdout, stderr = run_applescript(code)
        else:
            return jsonify({'error': 'Unsupported language'}), 400
    except Exception as e:
        os.chdir(initial_cwd)  # Change back to the initial directory if an exception occurs
        return jsonify({'error': f'Error running script: {str(e)}'}), 500
    finally:
        os.chdir(initial_cwd)  # Always change back to the initial directory

    response = {
        "exitCode": exit_code,
        "stdout": stdout,
        "stderr": stderr,
    }

    return jsonify(response), 200

@app.get("/logo.png")
async def plugin_logo():
    filename = 'logo.png'
    return await quart.send_file(filename, mimetype='image/png')

@app.get("/.well-known/ai-plugin.json")
async def plugin_manifest():
    host = request.headers['Host']
    with open("./.well-known/ai-plugin.json") as f:
        text = f.read()
        return quart.Response(text, mimetype="text/json")

@app.get("/openapi.yaml")
async def openapi_spec():
    host = request.headers['Host']
    with open("openapi.yaml") as f:
        text = f.read()
        return quart.Response(text, mimetype="text/yaml")

def main():
    app.run(debug=False, host="0.0.0.0", port=5004)

if __name__ == "__main__":
    main()
