from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from rag_chatbot_v3 import RAGChatbot
import logging
import os
from werkzeug.utils import secure_filename

app = Flask(__name__, template_folder='templates')
CORS(app)  # Enable CORS for all routes

# Configure upload folder
UPLOAD_FOLDER = 'docs/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Initialize the chatbot
try:
    # Ensure the chatbot is initialized with the correct path
    chatbot = RAGChatbot(app.config['UPLOAD_FOLDER'])
    print("Chatbot initialized successfully!")
except Exception as e:
    print(f"Error initializing chatbot: {str(e)}")
    chatbot = None

# Global chat history for the session (for simplicity, in a real app this would be per-user)
chat_history = []

@app.route('/')
def home():
    global chat_history
    chat_history = [] # Clear chat history on page load
    return render_template('index.html')

from flask import Response

@app.route('/ask', methods=['POST'])
def ask():
    global chat_history
    if not chatbot:
        return jsonify({'error': 'Chatbot not initialized properly'}), 500
    
    try:
        question = request.json.get('question')
        if not question:
            return jsonify({'error': 'No question provided'}), 400
        
        def generate():
            full_response = ""
            for chunk in chatbot.ask_stream(question, chat_history):
                full_response += chunk
                yield chunk # Send raw Markdown
        
            # Update chat history once after the full response is generated
            chat_history.append({"role": "user", "content": question})
            chat_history.append({"role": "bot", "content": full_response})

        return Response(generate(), mimetype='text/plain')

    except Exception as e:
        logging.error(f"Error processing question: {str(e)}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Running in production mode, disable debug and reloader for stability
    app.run(debug=False, use_reloader=False, port=5000)
