document.addEventListener('DOMContentLoaded', () => {
    const controlPanel = document.querySelector('.control-panel');
    const openPanelBtn = document.getElementById('open-panel-btn');
    const closePanelBtn = document.getElementById('close-panel-btn');
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    const fontIncBtn = document.getElementById('font-size-increase-btn');
    const fontDecBtn = document.getElementById('font-size-decrease-btn');
    const clearHistoryBtn = document.getElementById('clear-history-btn');
    const topicCardsContainer = document.getElementById('topic-cards-container');
    const favoritesList = document.getElementById('favorites-list');
    const chatWindow = document.getElementById('chat-window');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const newChatBtn = document.getElementById('new-chat-btn'); // Get the new chat button
    
    let currentFontSize = 16;
    const favorites = JSON.parse(localStorage.getItem('unaniFavorites')) || [];

    const topics = {
        "Basic Principles": [
            { name: 'Humors (Akhlat)', icon: 'fa-flask' },
            { name: 'Temperaments (Mizaj)', icon: 'fa-balance-scale' },
            { name: 'Faculties (Quwa)', icon: 'fa-brain' },
            { name: 'Organs (Aza)', icon: 'fa-heart' },
            { name: 'Spirits (Arwah)', icon: 'fa-wind' },
            { name: 'Functions (Af’al)', icon: 'fa-cogs' },
            { name: 'Causes of Disease (Asbab-e-Sitta Zarooriya)', icon: 'fa-bug' },
        ],
        "Diagnosis & Treatment": [
            { name: 'Pulse Examination (Nabz)', icon: 'fa-heartbeat' },
            { name: 'Urine Examination (Baul)', icon: 'fa-tint' },
            { name: 'Stool Examination (Baraz)', icon: 'fa-poop' },
            { name: 'Herbal Medicine (Advia Mufrada)', icon: 'fa-leaf' },
            { name: 'Compound Formulations (Advia Murakkaba)', icon: 'fa-pills' },
            { name: 'Regimental Therapy (Ilaj Bil Tadbeer)', icon: 'fa-spa' },
            { name: 'Dietotherapy (Ilaj Bil Ghiza)', icon: 'fa-apple-alt' },
            { name: 'Pharmacology (Ilmul Advia)', icon: 'fa-mortar-pestle' },
        ],
        "Specific Diseases & Remedies": [
            { name: 'Fever (Humma)', icon: 'fa-thermometer-full' },
            { name: 'Cough (Sual)', icon: 'fa-lungs' },
            { name: 'Headache (Suda)', icon: 'fa-head-side-mask' },
            { name: 'Digestive Disorders', icon: 'fa-stomach' },
            { name: 'Skin Diseases', icon: 'fa-hand-sparkles' },
            { name: 'Joint Pain (Waja-ul-Mafasil)', icon: 'fa-joint' },
            { name: 'Cardiac Ailments', icon: 'fa-heart-pulse' },
            { name: 'Respiratory Ailments', icon: 'fa-lungs' },
            { name: 'Urinary Disorders', icon: 'fa-kidneys' },
        ]
    };

    const topicSearch = document.getElementById('topic-search');

    function displayTopics(filter = '') {
        const normalizedFilter = filter.toLowerCase();
        topicCardsContainer.innerHTML = '';
        for (const category in topics) {
            const filteredTopics = topics[category].filter(topic => topic.name.toLowerCase().includes(normalizedFilter));
            if (filteredTopics.length > 0) {
                const categoryDiv = document.createElement('div');
                categoryDiv.className = 'topic-category';
                categoryDiv.innerHTML = `<h3>${category}</h3>`;
                const cardsDiv = document.createElement('div');
                cardsDiv.className = 'topic-cards';
                filteredTopics.forEach(topic => {
                    const card = document.createElement('div');
                    card.className = 'topic-card';
                    card.innerHTML = `
                        <i class="fas ${topic.icon}"></i>
                        <h4>${topic.name}</h4>
                        <button class="favorite-btn" data-topic="${topic.name}" aria-label="Add to favorites">
                            <i class="far fa-star"></i>
                        </button>
                    `;
                    card.addEventListener('click', () => selectTopic(topic.name));
                    cardsDiv.appendChild(card);
                });
                categoryDiv.appendChild(cardsDiv);
                topicCardsContainer.appendChild(categoryDiv);
            }
        }
        updateAllStarIcons();
    }

    topicSearch.addEventListener('input', (e) => {
        displayTopics(e.target.value);
    });

    function selectTopic(topicName) {
        addMessage(topicName, 'user');
        getBotResponse(topicName);
    }

    // --- Chat Functionality ---
    let chatHistory = [];

    function addMessage(text, sender) {
        const messageElem = document.createElement('div');
        messageElem.className = `message ${sender}-message`;
        // Use marked.parse for bot messages, plain text for user messages
        messageElem.innerHTML = `<p>${sender === 'bot' || sender === 'bot-initial' ? marked.parse(text) : text}</p>`;
        chatWindow.appendChild(messageElem);
        chatWindow.scrollTop = chatWindow.scrollHeight;
        chatHistory.push({ text, sender });
        saveChatHistory();
    }

    function saveChatHistory() {
        localStorage.setItem('unaniChatHistory', JSON.stringify(chatHistory));
    }

    function loadChatHistory() {
        const savedHistory = localStorage.getItem('unaniChatHistory');
        if (savedHistory) {
            chatHistory = JSON.parse(savedHistory);
            chatWindow.innerHTML = '';
            chatHistory.forEach(message => {
                const messageElem = document.createElement('div');
                messageElem.className = `message ${message.sender}-message`;
                messageElem.innerHTML = `<p>${message.text}</p>`;
                chatWindow.appendChild(messageElem);
            });
            chatWindow.scrollTop = chatWindow.scrollHeight;
        } else {
            addMessage("Hello! I'm your Unani Firdous Ul Hikmat assistant. Select a topic from the control panel or ask me a question.", 'bot-initial');
        }
    }

    function clearChatHistory() {
        chatHistory = [];
        localStorage.removeItem('unaniChatHistory');
        chatWindow.innerHTML = '';
        addMessage("Hello! I'm your Unani Firdous Ul Hikmat assistant. Select a topic from the control panel or ask me a question.", 'bot-initial');
    }

    clearHistoryBtn.addEventListener('click', clearChatHistory);
    newChatBtn.addEventListener('click', clearChatHistory); // Add event listener for new chat button

    function handleUserInput() {
        const text = userInput.value.trim();
        if (text) {
            addMessage(text, 'user');
            userInput.value = '';
            getBotResponse(text);
        }
    }

    async function getBotResponse(question) {
        showTypingIndicator();
        let botMessageElem = null; // To hold the bot's message element

        try {
            const response = await fetch('/ask', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ question: question }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            hideTypingIndicator();
            
            // Create a new message element for the bot's response
            botMessageElem = document.createElement('div');
            botMessageElem.className = 'message bot-message';
            const p = document.createElement('p');
            botMessageElem.appendChild(p);
            chatWindow.appendChild(botMessageElem);

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let fullResponse = '';

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value, { stream: true });
                fullResponse += chunk;
                p.innerHTML = marked.parse(fullResponse); // Use marked.parse to render Markdown
                chatWindow.scrollTop = chatWindow.scrollHeight;
            }

        } catch (error) {
            hideTypingIndicator();
            console.error('Error fetching bot response:', error);
            if (botMessageElem) {
                botMessageElem.querySelector('p').textContent = 'Sorry, I encountered an error. Please try again.';
            } else {
                addMessage('Sorry, I encountered an error. Please try again.', 'bot');
            }
        }
    }

    function showTypingIndicator() {
        const typingElem = document.createElement('div');
        typingElem.className = 'message bot-message typing-indicator';
        typingElem.innerHTML = `
            <span></span>
            <span></span>
            <span></span>
        `;
        chatWindow.appendChild(typingElem);
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    function hideTypingIndicator() {
        const typingElem = document.querySelector('.typing-indicator');
        if (typingElem) {
            typingElem.remove();
        }
    }

    sendBtn.addEventListener('click', handleUserInput);
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            handleUserInput();
        }
    });

    // --- Personalization & Accessibility ---
    function toggleTheme() {
        document.body.classList.toggle('light-mode');
        document.body.classList.toggle('dark-mode');
        const isLight = document.body.classList.contains('light-mode');
        localStorage.setItem('theme', isLight ? 'light' : 'dark');
        themeToggleBtn.innerHTML = isLight ? '<i class="fas fa-moon"></i>' : '<i class="fas fa-sun"></i>';
    }

    function changeFontSize(amount) {
        currentFontSize = Math.max(10, Math.min(22, currentFontSize + amount));
        document.documentElement.style.setProperty('--font-size-base', `${currentFontSize}px`);
        localStorage.setItem('fontSize', currentFontSize);
    }

    function toggleFavorite(topicName, starIcon) {
        const index = favorites.indexOf(topicName);
        if (index > -1) {
            favorites.splice(index, 1);
            starIcon.classList.remove('fas');
            starIcon.classList.add('far');
        } else {
            favorites.push(topicName);
            starIcon.classList.remove('far');
            starIcon.classList.add('fas');
        }
        localStorage.setItem('unaniFavorites', JSON.stringify(favorites));
        displayFavorites();
        updateAllStarIcons();
    }

    function displayFavorites() {
        favoritesList.innerHTML = '';
        favorites.forEach(topicName => {
            const li = document.createElement('li');
            li.textContent = topicName;
            li.addEventListener('click', () => selectTopic(topicName));
            favoritesList.appendChild(li);
        });
    }

    function updateAllStarIcons() {
        document.querySelectorAll('.favorite-btn').forEach(btn => {
            const topicName = btn.dataset.topic;
            const starIcon = btn.querySelector('i');
            if (favorites.includes(topicName)) {
                starIcon.classList.remove('far');
                starIcon.classList.add('fas');
            } else {
                starIcon.classList.remove('fas');
                starIcon.classList.add('far');
            }
        });
    }

    function loadPreferences() {
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme === 'light') {
            toggleTheme();
        }

        const savedFontSize = localStorage.getItem('fontSize');
        if (savedFontSize) {
            currentFontSize = parseInt(savedFontSize, 10);
            changeFontSize(0);
        }
        
        displayFavorites();
    }

    themeToggleBtn.addEventListener('click', toggleTheme);
    fontIncBtn.addEventListener('click', () => changeFontSize(1));
    fontDecBtn.addEventListener('click', () => changeFontSize(-1));
    openPanelBtn.addEventListener('click', () => {
        controlPanel.classList.remove('hidden');
    });

    closePanelBtn.addEventListener('click', () => {
        controlPanel.classList.add('hidden');
    });

    // --- Initialization ---
    displayTopics();
    loadChatHistory();
    loadPreferences();
    updateAllStarIcons();

});
