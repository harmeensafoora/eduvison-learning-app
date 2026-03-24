// EduVision - Frontend JavaScript
// State management and backend integration

// ============================================
// STATE MANAGEMENT
// ============================================

const AppState = {
  currentState: 'idle', // idle | processing | complete
  sessionId: null,
  documentData: null,
  
  setState(newState) {
    this.currentState = newState;
    document.querySelector('.page-shell').setAttribute('data-state', newState);
  },
  
  setSession(sessionId) {
    this.sessionId = sessionId;
  },
  
  setDocumentData(data) {
    this.documentData = data;
  }
};

// ============================================
// UTILITY FUNCTIONS
// ============================================

function showElement(id) {
  const el = document.getElementById(id);
  if (el) el.style.display = 'block';
}

function hideElement(id) {
  const el = document.getElementById(id);
  if (el) el.style.display = 'none';
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function setHTML(id, html) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = html;
}

// ============================================
// FILE UPLOAD HANDLING
// ============================================

const uploadZone = document.getElementById('uploadZone');
const fileInput = document.getElementById('pdfFile');
const fileChip = document.getElementById('fileChip');
const clearFileBtn = document.getElementById('clearFileBtn');
const uploadBtn = document.getElementById('uploadBtn');
const browseBtn = document.getElementById('browseBtn');

let selectedFile = null;
uploadBtn.disabled = true; // no file selected yet

// Drag and drop handlers
uploadZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  uploadZone.classList.add('drag-active');
});

uploadZone.addEventListener('dragleave', () => {
  uploadZone.classList.remove('drag-active');
});

uploadZone.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadZone.classList.remove('drag-active');
  
  const files = e.dataTransfer.files;
  if (files.length > 0 && files[0].type === 'application/pdf') {
    handleFileSelection(files[0]);
  } else {
    alert('Please upload a PDF file');
  }
});

// File input change handler
fileInput.addEventListener('change', (e) => {
  if (e.target.files.length > 0) {
    handleFileSelection(e.target.files[0]);
  }
});

// Browse button
browseBtn.addEventListener('click', () => {
  fileInput.click();
});

// Handle file selection
function handleFileSelection(file) {
  if (file.size > 50 * 1024 * 1024) { // 50MB limit
    alert('File size must be less than 50MB');
    return;
  }
  
  selectedFile = file;
  
  // Update UI
  document.getElementById('fileChipName').textContent = file.name;
  document.getElementById('fileChipMeta').textContent = `${(file.size / 1024 / 1024).toFixed(2)} MB`;
  fileChip.classList.add('active');
  uploadBtn.disabled = false;
}

// Clear file
clearFileBtn.addEventListener('click', () => {
  selectedFile = null;
  fileInput.value = '';
  fileChip.classList.remove('active');
  uploadBtn.disabled = true;
});

// ============================================
// DOCUMENT PROCESSING
// ============================================

uploadBtn.addEventListener('click', async () => {
  if (!selectedFile) return;
  
  const learningIntent = document.getElementById('learningIntent').value;
  
  try {
    // Switch to processing state
    AppState.setState('processing');
    
    // Update session info
    const sessionId = `session-${Date.now()}`;
    AppState.setSession(sessionId);
    setText('sessionIdText', sessionId);
    setText('sessionIntentText', learningIntent);
    setText('sessionPipelineText', 'Processing');
    
    // Create FormData
    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('learningIntent', learningIntent);
    formData.append('sessionId', sessionId);
    
    // Start processing
    await processDocument(formData);
    
  } catch (error) {
    console.error('Upload error:', error);
    alert('Failed to process document. Please try again.');
    AppState.setState('idle');
  }
});

async function processDocument(formData) {
  try {
    // Call the backend API
    const response = await fetch('/api/process', {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      throw new Error('Processing failed');
    }
    
    const data = await response.json();
    
    // Simulate the visual stages for UX (backend processes instantly)
    const stages = data.stages || [
      { id: 'extract', label: 'Extracting text and structure', duration: 1000 },
      { id: 'concepts', label: 'Identifying core concepts', duration: 1500 },
      { id: 'relationships', label: 'Mapping relationships', duration: 1000 },
      { id: 'visuals', label: 'Preparing visuals', duration: 1000 },
      { id: 'hooks', label: 'Generating study hooks', duration: 1000 }
    ];
    
    // Create stage elements
    const stageList = document.getElementById('processingStages');
    stageList.innerHTML = stages.map((stage) => `
      <div class="processing-stage" id="stage-${stage.id}">
        <div class="stage-dot"></div>
        <span class="stage-text">${stage.label}</span>
        <span class="stage-status">Pending</span>
      </div>
    `).join('');
    
    let totalDuration = 0;
    let completedDuration = 0;
    stages.forEach(s => totalDuration += (s.duration || 1000));
    
    // Animate through stages
    for (let i = 0; i < stages.length; i++) {
      const stage = stages[i];
      const stageEl = document.getElementById(`stage-${stage.id}`);
      
      // Mark as active
      stageEl.classList.add('active');
      stageEl.querySelector('.stage-status').textContent = 'Processing...';
      
      // Update progress
      const progress = Math.round((completedDuration / totalDuration) * 100);
      updateProgress(progress);
      
      // Wait for stage duration
      await new Promise(resolve => setTimeout(resolve, stage.duration || 1000));
      
      // Mark as complete
      stageEl.classList.remove('active');
      stageEl.classList.add('complete');
      stageEl.querySelector('.stage-status').textContent = 'Done';
      
      completedDuration += (stage.duration || 1000);
      
      // Add concept bubbles progressively
      if (i === 1 && data.concepts && data.concepts[0]) {
        addConceptBubble(data.concepts[0].name);
      } else if (i === 2 && data.concepts && data.concepts[1]) {
        addConceptBubble(data.concepts[1].name);
      } else if (i === 3 && data.concepts && data.concepts[2]) {
        addConceptBubble(data.concepts[2].name);
      }
    }
    
    // Final progress
    updateProgress(100);
    
    // Wait then load results
    await new Promise(resolve => setTimeout(resolve, 500));

    // Update AppState with the real server-assigned session ID
    if (data.sessionId) {
      AppState.setSession(data.sessionId);
    }

    // Load results with backend data
    loadResults(data);
    
  } catch (error) {
    console.error('Processing error:', error);
    alert('Failed to process document. Please try again.');
    AppState.setState('idle');
  }
}

function updateProgress(percent) {
  document.getElementById('progressFill').style.width = `${percent}%`;
  document.getElementById('progressValue').textContent = `${percent}%`;
}

function addConceptBubble(text) {
  const bubblesContainer = document.getElementById('conceptBubbles');
  
  // Remove empty state if present
  const emptyState = bubblesContainer.querySelector('.empty-state');
  if (emptyState) emptyState.remove();
  
  // Add bubble
  const bubble = document.createElement('span');
  bubble.className = 'concept-bubble';
  bubble.textContent = text;
  bubblesContainer.appendChild(bubble);
}

// ============================================
// LOAD RESULTS
// ============================================

function loadResults(data) {
  // Switch to complete state
  AppState.setState('complete');
  
  // Use backend data or fallback to mock
  const resultData = data || {
    mainTopic: 'Cell Structure',
    complexity: '59/100',
    studyTime: '10 min',
    visuals: 0,
    concepts: [
      { 
        id: 1, 
        name: 'Cell Structure',
        category: 'FOUNDATION',
        description: 'The cell membrane regulates material movement and preserves internal balance.'
      }
    ],
    summary: '## Default Summary\n\nNo data available.'
  };
  
  AppState.setDocumentData(resultData);
  
    // Update status bar
  setText('statusDocument', resultData.mainTopic);

  // Update summary with markdown
  if (typeof marked !== 'undefined') {
    setHTML('summaryList', marked.parse(resultData.summary));
  } else {
    setText('summaryList', resultData.summary);
  }
  
  // Update concept cards
  const conceptList = document.getElementById('conceptList');
  conceptList.innerHTML = resultData.concepts.map((concept, idx) => `
    <div class="concept-item" data-concept-id="${concept.id}" onclick="showConceptDetail('${concept.id}')">
      <div class="concept-name">${idx + 1}. ${concept.name}</div>
      <div class="concept-desc">${concept.summary || concept.name}</div>
    </div>
  `).join('');
  
  // Show confusion alert if points were detected
  const confusionAlert = document.getElementById('confusionAlert');
  const confusionPoints = resultData.confusionPoints || [];
  if (confusionPoints.length > 0 && confusionAlert) {
    confusionAlert.classList.add('active');
    const confusionText = document.getElementById('confusionText');
    if (confusionText) {
      confusionText.textContent = confusionPoints.map(p => `${p.concept}: ${p.tip}`).join(' • ');
    }
  } else if (confusionAlert) {
    confusionAlert.classList.remove('active');
  }

  // Draw knowledge graph
  drawKnowledgeGraph(resultData.concepts);

  // Status pill is already pill-ok in HTML — just update text
  setText('statusPill', 'Ready');
}

// ============================================
// KNOWLEDGE GRAPH
// ============================================

function drawKnowledgeGraph(concepts) {
  const svg = document.getElementById('knowledgeGraph');
  if (!concepts || concepts.length === 0) return;

  const width = 760;
  const height = 320;
  svg.innerHTML = '';

  // Circular layout centered in the SVG
  const cx = width / 2;
  const cy = height / 2;
  const r = concepts.length === 1 ? 0 : Math.min(cx - 60, cy - 50);
  const angleStep = (2 * Math.PI) / concepts.length;

  const positions = concepts.map((_, i) => ({
    x: cx + r * Math.cos(angleStep * i - Math.PI / 2),
    y: cy + r * Math.sin(angleStep * i - Math.PI / 2),
  }));

  const nodeColors = { foundation: '#ffccd5', bridge: '#f6b194', detail: '#fef08a', core: '#d4f0fc' };

  // Draw sequential connections
  for (let i = 0; i < concepts.length - 1; i++) {
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    line.setAttribute('x1', positions[i].x);
    line.setAttribute('y1', positions[i].y);
    line.setAttribute('x2', positions[i + 1].x);
    line.setAttribute('y2', positions[i + 1].y);
    line.setAttribute('stroke', '#d4d4d8');
    line.setAttribute('stroke-width', '1.5');
    svg.appendChild(line);
  }

  // Draw nodes
  concepts.forEach((concept, i) => {
    const pos = positions[i];
    const fill = nodeColors[concept.type] || nodeColors.core;
    const label = concept.name.length > 14 ? concept.name.slice(0, 13) + '…' : concept.name;

    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('cx', pos.x);
    circle.setAttribute('cy', pos.y);
    circle.setAttribute('r', '34');
    circle.setAttribute('fill', fill);
    circle.setAttribute('stroke', '#1c1917');
    circle.setAttribute('stroke-width', '1.5');
    circle.style.cursor = 'pointer';
    circle.onclick = () => showConceptDetail(concept.id);
    svg.appendChild(circle);

    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('x', pos.x);
    text.setAttribute('y', pos.y + 4);
    text.setAttribute('text-anchor', 'middle');
    text.setAttribute('dominant-baseline', 'middle');
    text.setAttribute('font-family', 'DM Sans, sans-serif');
    text.setAttribute('font-size', '10');
    text.setAttribute('font-weight', '700');
    text.setAttribute('pointer-events', 'none');
    text.textContent = label;
    svg.appendChild(text);
  });
}

// ============================================
// CONCEPT DETAIL
// ============================================

window.showConceptDetail = function(conceptId) {
  const concepts = AppState.documentData && AppState.documentData.concepts;
  if (!concepts) return;
  const concept = concepts.find(c => String(c.id) === String(conceptId));
  if (!concept) return;

  const detailPanel = document.getElementById('conceptDetailPanel');
  const bulletsHTML = concept.bullets && concept.bullets.length
    ? `<ul style="padding-left:1.2rem;margin-top:0.75rem;">${concept.bullets.map(b => `<li>${b}</li>`).join('')}</ul>`
    : '';
  detailPanel.innerHTML = `
    <h4>${concept.name}</h4>
    <p style="margin-top: 0.5rem;">${concept.summary || concept.name}</p>
    ${bulletsHTML}
  `;
  detailPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
};

// ============================================
// TAB SWITCHING
// ============================================

const tabButtons = document.querySelectorAll('.tab-btn');
const tabPanes = document.querySelectorAll('.tab-pane');

// Auto-load triggers for tabs that need a fetch on first visit
const TAB_AUTOLOAD = {
  details:    () => document.getElementById('detailsBtn').click(),
  images:     () => document.getElementById('loadImagesBtn').click(),
  references: () => document.getElementById('referencesBtn').click(),
  dashboard:  () => document.getElementById('loadDashboardBtn').click(),
};

tabButtons.forEach(button => {
  button.addEventListener('click', () => {
    const targetTab = button.getAttribute('data-tab');

    tabButtons.forEach(btn => btn.classList.remove('active'));
    button.classList.add('active');

    tabPanes.forEach(pane => pane.classList.remove('active'));
    const targetPane = document.getElementById(`tab-${targetTab}`);
    if (targetPane) targetPane.classList.add('active');

    // Auto-load on first visit (only when results are available)
    if (AppState.currentState === 'complete' && !button.dataset.loaded && TAB_AUTOLOAD[targetTab]) {
      button.dataset.loaded = '1';
      TAB_AUTOLOAD[targetTab]();
    }
  });
});

// ============================================
// DETAILS TAB
// ============================================

document.getElementById('detailsBtn').addEventListener('click', async () => {
  const detailsContent = document.getElementById('detailsContent');
  detailsContent.innerHTML = '<div class="loading-card">Generating detailed explanation...</div>';
  
  try {
    const formData = new FormData();
    formData.append('sessionId', AppState.sessionId);
    
    const response = await fetch('/api/generate-details', {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) throw new Error('Failed to generate details');
    
    const data = await response.json();
    
    if (typeof marked !== 'undefined') {
      detailsContent.innerHTML = marked.parse(data.content);
    } else {
      detailsContent.textContent = data.content;
    }
  } catch (error) {
    console.error('Details error:', error);
    detailsContent.innerHTML = '<p class="empty-state">Failed to load details. Please try again.</p>';
  }
});

// ============================================
// TRANSLATION TAB
// ============================================

document.getElementById('translateBtn').addEventListener('click', async () => {
  const language = document.getElementById('languageSelect').value;
  const translatedContent = document.getElementById('translatedContent');
  
  translatedContent.innerHTML = `<div class="loading-card">Translating to ${language}...</div>`;
  
  try {
    const formData = new FormData();
    formData.append('sessionId', AppState.sessionId);
    formData.append('language', language);
    
    const response = await fetch('/api/translate', {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) throw new Error('Translation failed');
    
    const data = await response.json();
    
    if (typeof marked !== 'undefined') {
      translatedContent.innerHTML = marked.parse(data.content);
    } else {
      translatedContent.textContent = data.content;
    }
  } catch (error) {
    console.error('Translation error:', error);
    translatedContent.innerHTML = '<p class="empty-state">Translation failed. Please try again.</p>';
  }
});

// ============================================
// IMAGES TAB
// ============================================

document.getElementById('loadImagesBtn').addEventListener('click', async () => {
  const imagesList = document.getElementById('imagesList');
  imagesList.innerHTML = '<div class="loading-card">Loading images...</div>';
  
  try {
    const formData = new FormData();
    formData.append('sessionId', AppState.sessionId);
    
    const response = await fetch('/api/load-images', {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) throw new Error('Failed to load images');
    
    const data = await response.json();
    
    if (data.images && data.images.length > 0) {
      // Display images
      imagesList.innerHTML = data.images.map((img) => `
        <div class="image-item">
          <img src="${img.url}" alt="${img.title}">
          <div>
            <strong>${img.title}</strong>
            <p>${img.description}</p>
          </div>
        </div>
      `).join('');
    } else {
      imagesList.innerHTML = '<p class="empty-state">No diagrams found in this document</p>';
    }
  } catch (error) {
    console.error('Images error:', error);
    imagesList.innerHTML = '<p class="empty-state">Failed to load images</p>';
  }
});

document.getElementById('labelImagesBtn').addEventListener('click', async () => {
  const imagesList = document.getElementById('imagesList');

  imagesList.innerHTML = '<div class="loading-card">Running AI analysis on images...</div>';

  try {
    const response = await fetch(`/images/label/${AppState.sessionId}`, {
      method: 'POST'
    });

    if (!response.ok) throw new Error('AI analysis failed');

    const data = await response.json();

    if (data.results && data.results.length > 0) {
      imagesList.innerHTML = data.results.map((item, i) => `
        <div class="image-item" onclick="showLabeledImage(${i})" data-original="${item.original}" data-labeled="${item.labeled_image_url || item.original}" data-organ="${item.organ || 'Unknown'}" data-labels="${(item.labels || []).join(', ')}">
          <img src="${item.original}" alt="Image ${i + 1}">
          <div>
            <strong>${item.organ || 'Unknown'}</strong>
            <p class="muted-text">${(item.labels || []).slice(0, 3).join(', ') || 'No labels'}</p>
          </div>
        </div>
      `).join('');
    } else {
      imagesList.innerHTML = '<p class="empty-state">No images found. Load images first.</p>';
    }
  } catch (error) {
    console.error('AI match error:', error);
    imagesList.innerHTML = '<p class="empty-state">AI analysis failed. Make sure images are loaded first.</p>';
  }
});

window.showLabeledImage = function(index) {
  const items = document.querySelectorAll('#imagesList .image-item');
  if (!items[index]) return;
  const item = items[index];
  const organ = item.dataset.organ;
  const labels = item.dataset.labels;
  const labeledSrc = item.dataset.labeled;
  const preview = document.getElementById('imagePreview');
  preview.innerHTML = `
    <h4 class="viewer-title">${organ}</h4>
    <img class="preview-image" src="${labeledSrc}" alt="${organ}">
    <p class="muted-text" style="margin-top:0.75rem;">${labels || 'No labels detected'}</p>
  `;
};

// ============================================
// REFERENCES TAB
// ============================================

document.getElementById('referencesBtn').addEventListener('click', async () => {
  const referencesList = document.getElementById('referencesList');
  referencesList.innerHTML = '<div class="loading-card">Building study roadmap...</div>';

  try {
    const formData = new FormData();
    formData.append('sessionId', AppState.sessionId);

    const response = await fetch('/api/generate-roadmap', {
      method: 'POST',
      body: formData
    });

    if (!response.ok) throw new Error('Failed to generate roadmap');

    const data = await response.json();
    const { before, after, byLevel } = data.roadmap;

    const renderTopicItems = (items) => items.map(item =>
      `<li><strong>${item.title}</strong>${item.subtitle ? ` — <span style="color:var(--muted);">${item.subtitle}</span>` : ''}</li>`
    ).join('');

    const renderResources = (resources) => {
      if (!resources || resources.length === 0) return '<p style="color:var(--muted);font-size:0.85rem;">No resources listed.</p>';
      return `<ul style="list-style:disc;padding-left:1.2rem;margin-top:0.4rem;">${resources.map(r =>
        `<li style="margin-bottom:0.5rem;"><strong>${r.title}</strong> <span style="color:var(--muted);font-size:0.75rem;">[${r.type || 'resource'}]</span><br><span style="color:var(--soft);font-size:0.82rem;">${r.reason || ''}</span></li>`
      ).join('')}</ul>`;
    };

    const lv = byLevel || {};
    referencesList.innerHTML = `
      <div class="card" style="margin-bottom:1rem;">
        <h4 style="margin-bottom:0.6rem;">Before This Chapter</h4>
        <ul style="list-style:disc;padding-left:1.2rem;">${renderTopicItems(before)}</ul>
      </div>
      <div class="card" style="margin-bottom:1rem;">
        <h4 style="margin-bottom:0.6rem;">After This Chapter</h4>
        <ul style="list-style:disc;padding-left:1.2rem;">${renderTopicItems(after)}</ul>
      </div>
      <div class="card">
        <h4 style="margin-bottom:0.75rem;">Resources by Level</h4>
        <div style="margin-bottom:0.75rem;">
          <strong style="font-size:0.82rem;text-transform:uppercase;letter-spacing:0.05em;">Beginner</strong>
          ${renderResources(lv.beginner)}
        </div>
        <div style="margin-bottom:0.75rem;">
          <strong style="font-size:0.82rem;text-transform:uppercase;letter-spacing:0.05em;">Intermediate</strong>
          ${renderResources(lv.intermediate)}
        </div>
        <div>
          <strong style="font-size:0.82rem;text-transform:uppercase;letter-spacing:0.05em;">Expert</strong>
          ${renderResources(lv.expert)}
        </div>
      </div>
    `;
  } catch (error) {
    console.error('Roadmap error:', error);
    referencesList.innerHTML = '<p class="empty-state">Failed to generate roadmap</p>';
  }
});

// ============================================
// QUIZ TAB
// ============================================

function renderQuestionInput(q) {
  const type = q.type || 'multiple_choice';
  if (type === 'short_answer' || type === 'fill_blank') {
    return `<div class="quiz-options"><input type="text" class="quiz-text-input" placeholder="Type your answer here..."></div>`;
  }
  if (!q.options || q.options.length === 0) {
    return `<div class="quiz-options"><input type="text" class="quiz-text-input" placeholder="Type your answer here..."></div>`;
  }
  return `<div class="quiz-options">${q.options.map(opt => `
    <label class="quiz-option">
      <input type="radio" name="q_${q.id}" value="${opt.id !== undefined ? opt.id : opt}">
      <span>${opt.text !== undefined ? opt.text : opt}</span>
    </label>
  `).join('')}</div>`;
}

document.getElementById('generateQuizBtn').addEventListener('click', async () => {
  const difficulty = document.getElementById('quizDifficulty').value;
  const quizContainer = document.getElementById('quizContainer');

  quizContainer.innerHTML = '<div class="loading-card">Generating quiz questions...</div>';

  try {
    const formData = new FormData();
    formData.append('sessionId', AppState.sessionId);
    formData.append('difficulty', difficulty);

    const response = await fetch('/api/generate-quiz', {
      method: 'POST',
      body: formData
    });

    if (!response.ok) throw new Error('Failed to generate quiz');

    const data = await response.json();

    if (!data.questions || data.questions.length === 0) {
      quizContainer.innerHTML = '<p class="empty-state">No questions generated. Try again.</p>';
      return;
    }

    const quizHTML = data.questions.map((q, index) => `
      <div class="quiz-question" data-question-id="${q.id}" data-question-type="${q.type || 'multiple_choice'}">
        <p class="quiz-q-num">Question ${index + 1}</p>
        <p class="quiz-q-text">${q.question}</p>
        ${renderQuestionInput(q)}
        <div class="quiz-feedback" style="display:none;"></div>
      </div>
    `).join('');

    quizContainer.innerHTML = quizHTML + '<button class="quiz-submit-btn" onclick="submitQuiz()">Submit Answers</button>';
  } catch (error) {
    console.error('Quiz error:', error);
    quizContainer.innerHTML = '<p class="empty-state">Failed to generate quiz. Please try again.</p>';
  }
});

window.submitQuiz = async function() {
  // Collect answers from all question types
  const answers = {};
  document.querySelectorAll('.quiz-question').forEach(qEl => {
    const qId = qEl.dataset.questionId;
    const qType = qEl.dataset.questionType;
    if (!qId) return;

    if (qType === 'short_answer' || qType === 'fill_blank') {
      const input = qEl.querySelector('.quiz-text-input');
      if (input && input.value.trim()) answers[qId] = input.value.trim();
    } else {
      const selected = qEl.querySelector('input[type="radio"]:checked');
      if (selected) answers[qId] = selected.value;
    }
  });

  if (Object.keys(answers).length === 0) {
    alert('Please answer at least one question before submitting.');
    return;
  }

  const submitBtn = document.querySelector('.quiz-submit-btn');
  if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Submitting...'; }

  try {
    const formData = new FormData();
    formData.append('sessionId', AppState.sessionId);
    formData.append('answers', JSON.stringify(answers));

    const response = await fetch('/api/submit-quiz', {
      method: 'POST',
      body: formData
    });

    if (!response.ok) throw new Error('Failed to submit quiz');

    const data = await response.json();

    // Show per-question feedback inline
    if (data.results) {
      data.results.forEach(result => {
        const qEl = document.querySelector(`.quiz-question[data-question-id="${result.questionId}"]`);
        if (!qEl) return;
        const feedbackEl = qEl.querySelector('.quiz-feedback');
        feedbackEl.style.display = 'block';
        if (result.isCorrect) {
          feedbackEl.className = 'quiz-feedback correct';
          feedbackEl.textContent = '✓ Correct!';
        } else {
          feedbackEl.className = 'quiz-feedback incorrect';
          feedbackEl.innerHTML = `✗ Incorrect — correct answer: <strong>${result.correctAnswer || '–'}</strong>`;
        }
      });
    }

    // Score banner at the top
    const existing = document.getElementById('quizScoreBanner');
    if (existing) existing.remove();
    const banner = document.createElement('div');
    banner.id = 'quizScoreBanner';
    banner.className = 'quiz-score-banner';
    banner.innerHTML = `${data.score} / ${data.total} correct &nbsp;<span style="font-family:DM Sans,sans-serif;font-size:0.9rem;color:var(--muted);">(${data.percentage}%)</span>`;
    document.getElementById('quizContainer').prepend(banner);

    if (submitBtn) { submitBtn.textContent = 'Retake Quiz'; submitBtn.disabled = false; submitBtn.onclick = () => document.getElementById('generateQuizBtn').click(); }
  } catch (error) {
    console.error('Submit error:', error);
    if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Submit Answers'; }
    alert('Failed to submit quiz. Please try again.');
  }
};

// ============================================
// DASHBOARD TAB
// ============================================

document.getElementById('loadDashboardBtn').addEventListener('click', async () => {
  const dashboardContent = document.getElementById('dashboardContent');
  
  dashboardContent.innerHTML = '<div class="loading-card">Loading analytics...</div>';
  
  try {
    const formData = new FormData();
    formData.append('sessionId', AppState.sessionId);
    
    const response = await fetch('/api/load-dashboard', {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) throw new Error('Failed to load dashboard');
    
    const data = await response.json();
    
    const strengths = data.analytics.strengths || [];
    const needsPractice = data.analytics.needsPractice || [];

    const renderTopicList = (topics, emptyMsg) => topics.length > 0
      ? `<ul>${topics.map(t => `<li>${t}</li>`).join('')}</ul>`
      : `<p class="empty-hint">${emptyMsg}</p>`;

    const dashboardHTML = `
      <div class="dash-metrics">
        <div class="metric-card">
          <div class="metric-label">Progress</div>
          <div class="metric-val">${data.analytics.progress}%</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Quizzes Taken</div>
          <div class="metric-val">${data.analytics.quizzesTaken}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Avg. Accuracy</div>
          <div class="metric-val">${data.analytics.accuracy}%</div>
        </div>
      </div>

      <div class="dash-two">
        <div class="dash-panel">
          <h4>Your Strengths</h4>
          ${renderTopicList(strengths, 'Score 70%+ on a quiz to see your strengths here.')}
        </div>
        <div class="dash-panel">
          <h4>Needs More Practice</h4>
          ${renderTopicList(needsPractice, 'No weak areas detected yet — keep quizzing!')}
        </div>
      </div>

      <div class="dash-two">
        ${data.analytics.recommendations.map(rec => `
          <div class="rec-card">
            <h4>${rec.title}</h4>
            <p>${rec.message}</p>
          </div>
        `).join('')}
      </div>
    `;
    
    dashboardContent.innerHTML = dashboardHTML;
  } catch (error) {
    console.error('Dashboard error:', error);
    dashboardContent.innerHTML = '<p class="empty-state">Failed to load analytics</p>';
  }
});

// ============================================
// SUMMARY ACTIONS
// ============================================

document.getElementById('exportSummaryBtn').addEventListener('click', (e) => {
  if (AppState.documentData && AppState.documentData.summary) {
    navigator.clipboard.writeText(AppState.documentData.summary).catch(() => {});
    const btn = e.currentTarget;
    const original = btn.textContent;
    btn.textContent = 'Copied!';
    setTimeout(() => { btn.textContent = original; }, 1800);
  }
});

document.getElementById('generateQuizShortcut').addEventListener('click', () => {
  // Switch to quiz tab
  const quizTab = document.querySelector('[data-tab="quiz"]');
  if (quizTab) quizTab.click();
});

// ============================================
// NEW SESSION
// ============================================

document.getElementById('newSessionBtn').addEventListener('click', () => {
  window.location.reload();
});

// ============================================
// TYPEWRITER TAGLINE
// ============================================

(function initTypewriter() {
  const el = document.getElementById('typewriterText');
  if (!el) return;

  const phrases = [
    'Stop reading. Start understanding.',
    'Upload a chapter. Ace the exam.',
    'Turn dense notes into clear ideas.',
    'Map concepts. Test knowledge.',
    'Study smarter, not harder.',
    'Your PDF, transformed.',
  ];

  let phraseIdx = 0, charIdx = 0, deleting = false;

  function tick() {
    const phrase = phrases[phraseIdx];
    if (deleting) {
      charIdx--;
      el.textContent = phrase.slice(0, charIdx);
      if (charIdx === 0) {
        deleting = false;
        phraseIdx = (phraseIdx + 1) % phrases.length;
        setTimeout(tick, 320);
        return;
      }
      setTimeout(tick, 26);
    } else {
      charIdx++;
      el.textContent = phrase.slice(0, charIdx);
      if (charIdx === phrase.length) {
        setTimeout(() => { deleting = true; tick(); }, 2400);
        return;
      }
      setTimeout(tick, 54);
    }
  }

  setTimeout(tick, 800);
})();

// ============================================
// CONFUSION ALERT
// ============================================

const viewConfusionBtn = document.getElementById('viewConfusionBtn');
if (viewConfusionBtn) {
  viewConfusionBtn.addEventListener('click', () => {
    const detailsTab = document.querySelector('[data-tab="details"]');
    if (detailsTab) detailsTab.click();
  });
}

// ============================================
// INITIALIZE
// ============================================

console.log('EduVision initialized');