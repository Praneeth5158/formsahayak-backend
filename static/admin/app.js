document.addEventListener('DOMContentLoaded', () => {
    // --- STATE MANAGEMENT ---
    let apiToken = localStorage.getItem('admin_token') || '';
    let currentTab = 'overview';
    let trendChart = null;
    let searchTimeout = null;

    // --- DOM ELEMENTS ---
    const loginContainer = document.getElementById('login-container');
    const dashboardContainer = document.getElementById('dashboard-container');
    const loginForm = document.getElementById('login-form');
    const loginError = document.getElementById('login-error');
    const errorText = document.getElementById('error-text');
    const logoutBtn = document.getElementById('logout-btn');
    const timeDisplay = document.getElementById('current-time');
    const tabTitle = document.getElementById('tab-title');
    const tabSubtitle = document.getElementById('tab-subtitle');
    const navLinks = document.querySelectorAll('.nav-link');
    const tabPanels = document.querySelectorAll('.tab-panel');

    // Stats
    const statUsers = document.getElementById('stat-total-users');
    const statForms = document.getElementById('stat-total-forms');
    const statOcr = document.getElementById('stat-total-ocr');
    const statFeedback = document.getElementById('stat-total-feedback');
    const statActive = document.getElementById('stat-active-users');

    // Users Tab
    const userSearchInput = document.getElementById('user-search-input');
    const usersTableBody = document.getElementById('users-table-body');

    // Forms Tab
    const formsTableBody = document.getElementById('forms-table-body');

    // Feedback Tab
    const feedbackCardsContainer = document.getElementById('feedback-cards-container');

    // Modal Details
    const formModal = document.getElementById('form-details-modal');
    const closeModalBtn = document.getElementById('close-modal-btn');
    const modalUserEmail = document.getElementById('modal-user-email');
    const modalFileName = document.getElementById('modal-file-name');
    const modalUploadedAt = document.getElementById('modal-uploaded-at');
    const modalFormImage = document.getElementById('modal-form-image');
    const modalAudioPlayer = document.getElementById('modal-audio-player');
    const modalPdfLink = document.getElementById('modal-pdf-link');
    const modalExtractedText = document.getElementById('modal-extracted-text');
    const modalGuidanceText = document.getElementById('modal-guidance-text');

    // --- INITIATION / AUTHENTICATION ---
    if (apiToken) {
        verifySessionAndLoad();
    } else {
        showLogin();
    }

    // Live clock
    setInterval(() => {
        const now = new Date();
        timeDisplay.textContent = now.toLocaleTimeString();
    }, 1000);

    // Login Form Submit
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('admin-email').value.trim();
        const password = document.getElementById('admin-password').value;

        loginError.classList.add('hide');

        try {
            const response = await fetch('/api/admin/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ email, password })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Authentication failed');
            }

            const data = await response.json();
            apiToken = data.access_token;
            localStorage.setItem('admin_token', apiToken);
            showDashboard();
            loadTabContent('overview');
        } catch (err) {
            errorText.textContent = err.message;
            loginError.classList.remove('hide');
        }
    });

    // Logout click
    logoutBtn.addEventListener('click', () => {
        apiToken = '';
        localStorage.removeItem('admin_token');
        showLogin();
    });

    // --- NAVIGATION MANAGEMENT ---
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const targetTab = link.getAttribute('data-tab');
            
            navLinks.forEach(l => l.classList.remove('active'));
            link.classList.add('active');

            tabPanels.forEach(panel => panel.classList.remove('active'));
            document.getElementById(`panel-${targetTab}`).classList.add('active');

            currentTab = targetTab;
            updateHeaderTitles(targetTab);
            loadTabContent(targetTab);
        });
    });

    function updateHeaderTitles(tab) {
        if (tab === 'overview') {
            tabTitle.textContent = 'Overview';
            tabSubtitle.textContent = 'Dashboard statistics and system analytics';
        } else if (tab === 'users') {
            tabTitle.textContent = 'User Profiles';
            tabSubtitle.textContent = 'Browse and search registered user accounts';
        } else if (tab === 'forms') {
            tabTitle.textContent = 'Form & OCR Logs';
            tabSubtitle.textContent = 'Audit uploaded files and extracted OCR text';
        } else if (tab === 'feedback') {
            tabTitle.textContent = 'App Feedback';
            tabSubtitle.textContent = 'User ratings and app performance feedback';
        }
    }

    // --- API CLIENT HELPERS ---
    async function authorizedFetch(url, options = {}) {
        options.headers = {
            ...options.headers,
            'Authorization': `Bearer ${apiToken}`
        };

        const response = await fetch(url, options);

        if (response.status === 401 || response.status === 403) {
            // Expired or invalid token, force logout
            apiToken = '';
            localStorage.removeItem('admin_token');
            showLogin();
            throw new Error('Session expired. Please sign in again.');
        }

        return response;
    }

    async function verifySessionAndLoad() {
        try {
            const response = await authorizedFetch('/api/admin/stats');
            if (response.ok) {
                showDashboard();
                loadTabContent('overview');
            }
        } catch (err) {
            console.error('Session validation failed', err);
            showLogin();
        }
    }

    function showLogin() {
        loginContainer.classList.remove('hide');
        dashboardContainer.classList.add('hide');
    }

    function showDashboard() {
        loginContainer.classList.add('hide');
        dashboardContainer.classList.remove('hide');
    }

    // --- TAB LOAD CONTROLLERS ---
    function loadTabContent(tab) {
        if (tab === 'overview') {
            fetchStats();
        } else if (tab === 'users') {
            fetchUsers();
        } else if (tab === 'forms') {
            fetchForms();
        } else if (tab === 'feedback') {
            fetchFeedback();
        }
    }

    // --- 1. OVERVIEW DATA & CHART ---
    async function fetchStats() {
        try {
            const response = await authorizedFetch('/api/admin/stats');
            const data = await response.json();

            // Populate counts
            statUsers.textContent = data.total_users;
            statForms.textContent = data.total_forms;
            statOcr.textContent = data.total_ocr_scans;
            statFeedback.textContent = data.total_feedback;
            statActive.textContent = data.active_users;

            // Render Chart
            renderChart(data.analytics);
        } catch (err) {
            console.error('Failed to load overview statistics', err);
        }
    }

    function renderChart(analyticsData) {
        const ctx = document.getElementById('uploads-trend-chart').getContext('2d');
        
        if (trendChart) {
            trendChart.destroy();
        }

        const dates = analyticsData.upload_dates || [];
        const counts = analyticsData.upload_counts || [];

        if (dates.length === 0) {
            // Fallback empty view values
            dates.push(new Date().toLocaleDateString());
            counts.push(0);
        }

        // Creating gradient colors
        const purpleGradient = ctx.createLinearGradient(0, 0, 0, 300);
        purpleGradient.addColorStop(0, 'rgba(99, 102, 241, 0.45)');
        purpleGradient.addColorStop(1, 'rgba(99, 102, 241, 0.01)');

        trendChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: dates,
                datasets: [{
                    label: 'Uploaded Forms',
                    data: counts,
                    borderColor: '#6366f1',
                    borderWidth: 3,
                    pointBackgroundColor: '#6366f1',
                    pointBorderColor: 'rgba(255, 255, 255, 0.3)',
                    pointHoverRadius: 6,
                    pointRadius: 4,
                    fill: true,
                    backgroundColor: purpleGradient,
                    tension: 0.35
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: '#111928',
                        titleColor: '#f3f4f6',
                        bodyColor: '#9ca3af',
                        borderColor: 'rgba(255,255,255,0.08)',
                        borderWidth: 1,
                        padding: 12,
                        displayColors: false
                    }
                },
                scales: {
                    x: {
                        grid: {
                            color: 'rgba(255, 255, 255, 0.04)',
                            drawBorder: false
                        },
                        ticks: {
                            color: '#9ca3af',
                            font: { size: 11 }
                        }
                    },
                    y: {
                        grid: {
                            color: 'rgba(255, 255, 255, 0.04)',
                            drawBorder: false
                        },
                        ticks: {
                            color: '#9ca3af',
                            font: { size: 11 },
                            stepSize: 1
                        },
                        beginAtZero: true
                    }
                }
            }
        });
    }

    // --- 2. USERS DATA & SEARCH ---
    async function fetchUsers(searchQuery = '') {
        usersTableBody.innerHTML = `
            <tr>
                <td colspan="5" class="loading-state">
                    <i class="fa-solid fa-circle-notch fa-spin"></i> Loading users...
                </td>
            </tr>
        `;

        try {
            let url = '/api/admin/users';
            if (searchQuery) {
                url += `?query=${encodeURIComponent(searchQuery)}`;
            }

            const response = await authorizedFetch(url);
            const data = await response.json();
            const users = data.users || [];

            if (users.length === 0) {
                usersTableBody.innerHTML = `
                    <tr>
                        <td colspan="5" class="no-data-state">
                            No users found matching current filters.
                        </td>
                    </tr>
                `;
                return;
            }

            usersTableBody.innerHTML = '';
            users.forEach(user => {
                const tr = document.createElement('tr');
                const avatarContent = user.profile_image 
                    ? `<img src="${user.profile_image}" alt="${user.name}" onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22100%22 height=%22100%22 viewBox=%220 0 100 100%22><rect width=%22100%22 height=%22100%22 fill=%22%236366f1%22/><text x=%2250%22 y=%2255%22 font-family=%22sans-serif%22 font-size=%2240%22 fill=%22white%22 text-anchor=%22middle%22 dominant-baseline=%22middle%22>${user.name.charAt(0).toUpperCase()}</text></svg>'">`
                    : `<i class="fa-regular fa-user" style="color:var(--color-primary)"></i>`;

                tr.innerHTML = `
                    <td>
                        <div class="user-row-avatar">
                            ${avatarContent}
                        </div>
                    </td>
                    <td><strong>${escapeHtml(user.name)}</strong></td>
                    <td>${escapeHtml(user.email)}</td>
                    <td>${escapeHtml(user.phone || 'N/A')}</td>
                    <td><span class="badge">${escapeHtml(user.language || 'English')}</span></td>
                `;
                usersTableBody.appendChild(tr);
            });

        } catch (err) {
            console.error('Failed to search or load users list', err);
            usersTableBody.innerHTML = `
                <tr>
                    <td colspan="5" class="no-data-state" style="color:var(--color-danger)">
                        Error loading user records.
                    </td>
                </tr>
            `;
        }
    }

    // Debounced search trigger
    userSearchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        const query = e.target.value.trim();
        searchTimeout = setTimeout(() => {
            fetchUsers(query);
        }, 300);
    });

    // --- 3. FORMS DATA & DETAILS VIEWER ---
    async function fetchForms() {
        formsTableBody.innerHTML = `
            <tr>
                <td colspan="6" class="loading-state">
                    <i class="fa-solid fa-circle-notch fa-spin"></i> Loading uploaded forms...
                </td>
            </tr>
        `;

        try {
            const response = await authorizedFetch('/api/admin/forms');
            const data = await response.json();
            const forms = data.forms || [];

            if (forms.length === 0) {
                formsTableBody.innerHTML = `
                    <tr>
                        <td colspan="6" class="no-data-state">
                            No forms uploaded yet.
                        </td>
                    </tr>
                `;
                return;
            }

            formsTableBody.innerHTML = '';
            forms.forEach(form => {
                const tr = document.createElement('tr');
                const hasOcr = form.extracted_text && form.extracted_text !== 'PDF uploaded';
                const statusBadge = hasOcr
                    ? `<span class="status-pill success"><i class="fa-solid fa-check"></i> OCR Success</span>`
                    : (form.file_name.toLowerCase().endsWith('.pdf') 
                        ? `<span class="status-pill success"><i class="fa-regular fa-file-pdf"></i> PDF File</span>`
                        : `<span class="status-pill pending"><i class="fa-solid fa-spinner"></i> No OCR Data</span>`);

                const dateStr = new Date(form.created_at).toLocaleString();

                tr.innerHTML = `
                    <td>${form.id}</td>
                    <td><strong>${escapeHtml(form.user_email)}</strong></td>
                    <td>${escapeHtml(form.file_name)}</td>
                    <td>${dateStr}</td>
                    <td>${statusBadge}</td>
                    <td>
                        <button class="btn btn-secondary btn-sm view-details-btn" data-id="${form.id}">
                            <i class="fa-regular fa-eye"></i> Details
                        </button>
                    </td>
                `;

                // Add event listener to the details button
                const btn = tr.querySelector('.view-details-btn');
                btn.addEventListener('click', () => {
                    openFormDetailsModal(form);
                });

                formsTableBody.appendChild(tr);
            });
        } catch (err) {
            console.error('Failed to load forms list', err);
            formsTableBody.innerHTML = `
                <tr>
                    <td colspan="6" class="no-data-state" style="color:var(--color-danger)">
                        Error loading form history.
                    </td>
                </tr>
            `;
        }
    }

    function openFormDetailsModal(form) {
        modalUserEmail.textContent = form.user_email;
        modalFileName.textContent = form.file_name;
        modalUploadedAt.textContent = new Date(form.created_at).toLocaleString();
        modalExtractedText.textContent = form.extracted_text || 'No text extracted.';
        
        // Render guidance text or warning
        if (form.guidance_text) {
            modalGuidanceText.innerHTML = formatGuidanceHtml(form.guidance_text);
        } else {
            modalGuidanceText.innerHTML = '<p class="text-muted">No guidance text available.</p>';
        }

        // Set image source
        if (form.file_name.toLowerCase().endsWith('.pdf')) {
            modalFormImage.src = 'data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22200%22 height=%22200%22 viewBox=%220 0 100 100%22><rect width=%22100%22 height=%22100%22 fill=%22%231e293b%22/><text x=%2250%22 y=%2245%22 font-family=%22sans-serif%22 font-size=%2225%22 fill=%22%239ca3af%22 text-anchor=%22middle%22>PDF FILE</text><text x=%2250%22 y=%2265%22 font-family=%22sans-serif%22 font-size=%2212%22 fill=%22%236b7280%22 text-anchor=%22middle%22>Click PDF link to view</text></svg>';
        } else {
            modalFormImage.src = form.file_url || '';
        }

        // Setup audio player
        if (form.audio_path) {
            modalAudioPlayer.src = form.audio_path;
            modalAudioPlayer.style.display = 'block';
        } else {
            modalAudioPlayer.style.display = 'none';
        }

        // Setup PDF download link
        if (form.pdf_path) {
            modalPdfLink.href = form.pdf_path;
            modalPdfLink.style.display = 'inline-flex';
        } else {
            modalPdfLink.style.display = 'none';
        }

        // Show modal
        formModal.classList.remove('hide');
    }

    closeModalBtn.addEventListener('click', () => {
        formModal.classList.add('hide');
        // Stop audio playback
        modalAudioPlayer.pause();
        modalAudioPlayer.src = '';
    });

    // Close modal on click outside content
    window.addEventListener('click', (e) => {
        if (e.target === formModal) {
            formModal.classList.add('hide');
            modalAudioPlayer.pause();
            modalAudioPlayer.src = '';
        }
    });

    // Helper to format AI Guidance text with paragraphs
    function formatGuidanceHtml(text) {
        return text
            .split('\n')
            .map(line => {
                const trimmed = line.trim();
                if (!trimmed) return '';
                if (trimmed.match(/^\d+\./)) {
                    return `<p style="margin-bottom:8px; padding-left:12px; border-left:2px solid var(--color-primary);"><strong>${escapeHtml(trimmed)}</strong></p>`;
                }
                return `<p style="margin-bottom:8px;">${escapeHtml(trimmed)}</p>`;
            })
            .join('');
    }

    // --- 4. FEEDBACK DATA CARDS ---
    async function fetchFeedback() {
        feedbackCardsContainer.innerHTML = `
            <div class="loading-state">
                <i class="fa-solid fa-circle-notch fa-spin"></i> Loading feedback...
            </div>
        `;

        try {
            const response = await authorizedFetch('/api/admin/feedback');
            const data = await response.json();
            const feedbacks = data.feedback || [];

            if (feedbacks.length === 0) {
                feedbackCardsContainer.innerHTML = `
                    <div class="no-data-state" style="grid-column: 1 / -1;">
                        No user feedback entries found in database.
                    </div>
                `;
                return;
            }

            feedbackCardsContainer.innerHTML = '';
            feedbacks.forEach(fb => {
                const card = document.createElement('div');
                card.className = 'feedback-card glass-panel';

                const dateStr = new Date(fb.created_at).toLocaleDateString();
                
                // Parse rating value to stars representation
                const ratingNum = parseInt(fb.rating) || 0;
                let starsHtml = '';
                if (ratingNum >= 1 && ratingNum <= 5) {
                    for (let i = 1; i <= 5; i++) {
                        starsHtml += i <= ratingNum 
                            ? `<i class="fa-solid fa-star"></i>` 
                            : `<i class="fa-regular fa-star"></i>`;
                    }
                } else {
                    starsHtml = fb.rating ? `<strong>${escapeHtml(fb.rating)}</strong>` : 'N/A';
                }

                card.innerHTML = `
                    <div class="feedback-card-header">
                        <div class="feedback-user">
                            <h4 title="${escapeHtml(fb.user_email)}">${escapeHtml(fb.user_email)}</h4>
                            <div class="feedback-stars">${starsHtml}</div>
                        </div>
                        <span class="feedback-date">${dateStr}</span>
                    </div>
                    
                    <div class="feedback-metric">
                        <div>
                            <span>Experience:</span>
                            <strong>${escapeHtml(fb.app_experience || 'N/A')}</strong>
                        </div>
                        <div>
                            <span>Helpful Voice:</span>
                            <strong>${escapeHtml(fb.voice_guidance_helpful || 'N/A')}</strong>
                        </div>
                        <div>
                            <span>Would Recommend:</span>
                            <strong>${escapeHtml(fb.recommend_app || 'N/A')}</strong>
                        </div>
                    </div>
                    
                    <p class="feedback-comment">
                        ${escapeHtml(fb.additional_comments || fb.feedback_text || 'No comments left.')}
                    </p>
                `;
                feedbackCardsContainer.appendChild(card);
            });
        } catch (err) {
            console.error('Failed to load feedback entries', err);
            feedbackCardsContainer.innerHTML = `
                <div class="no-data-state" style="grid-column: 1 / -1; color: var(--color-danger);">
                    Error loading feedback logs.
                </div>
            `;
        }
    }

    // --- HTML ESCAPER HELPER ---
    function escapeHtml(str) {
        if (typeof str !== 'string') return str || '';
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }
});
