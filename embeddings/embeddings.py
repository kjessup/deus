import sys
import redis
import openai
import numpy as np
from transformers import AutoTokenizer, AutoModel

openai.api_key = "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"

def get_embeddings(string, method):
    if method == "codebert":
        tokenizer = AutoTokenizer.from_pretrained("microsoft/codebert-base")
        model = AutoModel.from_pretrained("microsoft/codebert-base")
        inputs = tokenizer(string, return_tensors='pt', truncation=True, padding=True)
        embeddings = model(**inputs).last_hidden_state.mean(dim=1).detach().numpy()
        return embeddings
    elif method == "openai":
        response = openai.Embedding.create(model="text-embedding-ada-002", input=string).get("data")
        embeddings = np.array([embedding_data["embedding"] for embedding_data in response])
        return embeddings
    else:
        print(f"Unknown method '{method}'. Supported methods: openai, codebert")
        sys.exit(1)

def put_embedding(key, value, method = "openai"):
    if key.strip() and value.strip():
        redis_conn = redis.Redis(host='localhost', port=6379, db=0)
        embeddings = get_embeddings(key, method)
        for i, embedding in enumerate(embeddings):
            redis_key = f'{key}:embedding:{i}'
            redis_conn.set(redis_key, embedding.tobytes())
            redis_key = f'{key}:value:{i}'
            redis_conn.set(redis_key, value)
        return 1
    return 0

def cosine_similarity(a, b):
    a = a.flatten()
    b = b.flatten()
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    return dot_product / (norm_a * norm_b)

def search_embeddings(key, similarity_threshold=0.7, method = "openai"):
    redis_conn = redis.Redis(host='localhost', port=6379, db=0)
    search_embedding = get_embeddings(key, method)
    search_results = []

    for key in redis_conn.scan_iter('*:embedding:*'):
        embedding_bytes = redis_conn.get(key)
        embedding = np.frombuffer(embedding_bytes, dtype=search_embedding.dtype).reshape(-1, search_embedding.shape[-1])
        similarity = cosine_similarity(search_embedding, embedding)

        if similarity >= similarity_threshold:
            str = key.decode('utf-8')
            splt = str.split(':')
            value = redis_conn.get(f'{splt[0]}:value:{splt[-1]}')
            search_results.append((f'{splt[0]}\n{value}\n\n', similarity))

    search_results.sort(key=lambda x: x[1], reverse=True)
    return search_results
