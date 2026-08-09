// Main Client JavaScript for Dynamic Interactive Elements

function dismissAlert(alertElement) {
    if (!alertElement) return;
    alertElement.classList.add('toast-dismissing');
    setTimeout(() => {
        if (alertElement.parentNode) {
            alertElement.remove();
        }
    }, 300);
}

function showToast(message, category = 'info') {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'fixed top-5 left-1/2 -translate-x-1/2 z-50 flex flex-col space-y-3 max-w-lg w-full px-4 pointer-events-none';
        document.body.appendChild(container);
    }

    let bgStyle = 'bg-slate-900/90 border-sky-500/40 text-sky-300 shadow-sky-500/10';
    let iconStyle = 'fa-circle-info text-sky-400';

    if (category === 'success') {
        bgStyle = 'bg-slate-900/90 border-emerald-500/40 text-emerald-300 shadow-emerald-500/10';
        iconStyle = 'fa-circle-check text-emerald-400';
    } else if (category === 'danger' || category === 'error') {
        bgStyle = 'bg-slate-900/90 border-rose-500/40 text-rose-300 shadow-rose-500/10';
        iconStyle = 'fa-triangle-exclamation text-rose-400';
    } else if (category === 'warning') {
        bgStyle = 'bg-slate-900/90 border-amber-500/40 text-amber-300 shadow-amber-500/10';
        iconStyle = 'fa-triangle-exclamation text-amber-400';
    }

    const toast = document.createElement('div');
    toast.className = `flash-alert pointer-events-auto p-4 rounded-xl border ${bgStyle} flex items-start justify-between shadow-2xl backdrop-blur-md float-toast-anim`;
    toast.innerHTML = `
        <div class="flex items-start space-x-3 pr-2">
            <i class="fa-solid ${iconStyle} text-lg mt-0.5 flex-shrink-0"></i>
            <span class="text-sm font-medium leading-snug break-words text-slate-100">${message}</span>
        </div>
        <button onclick="dismissAlert(this.parentElement)" class="text-slate-400 hover:text-white transition-colors p-1 -mr-1 -mt-1 flex-shrink-0">
            <i class="fa-solid fa-xmark text-base"></i>
        </button>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        dismissAlert(toast);
    }, 6000);
}

document.addEventListener('DOMContentLoaded', () => {
    // Auto-dismiss floating alerts after 6 seconds
    const alerts = document.querySelectorAll('.flash-alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            dismissAlert(alert);
        }, 6000);
    });
});

// AJAX Task Completion Toggle
async function toggleTask(dateStr, taskId, element) {
    const labelSpan = element.closest('.task-item').querySelector('.task-text');
    try {
        const response = await fetch('/api/daily/task/toggle', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ date: dateStr, task_id: taskId })
        });
        const data = await response.json();
        if (data.success) {
            if (data.completed) {
                labelSpan.classList.add('line-through-fade');
            } else {
                labelSpan.classList.remove('line-through-fade');
            }

            if (typeof sortTasksInDOM === 'function') {
                sortTasksInDOM();
            } else {
                sortDashboardTasksInDOM();
            }

            // Sync dashboard stats if present
            const countEl = document.getElementById('dash-task-count');
            const pctEl = document.getElementById('dash-task-pct');
            const barEl = document.getElementById('dash-task-bar');
            if (countEl && pctEl && barEl) {
                const checkboxes = document.querySelectorAll('.task-item input[type="checkbox"]');
                const total = checkboxes.length;
                const completed = Array.from(checkboxes).filter(cb => cb.checked).length;
                const pct = total > 0 ? Math.round((completed / total) * 100) : 0;

                countEl.innerText = `${completed}/${total}`;
                pctEl.innerText = `(${pct}%)`;
                barEl.style.width = `${pct}%`;
            }
        } else {
            console.error('Task toggle failed:', data.message);
            showToast(data.message || 'Task toggle failed', 'danger');
        }
    } catch (err) {
        console.error('Error toggling task:', err);
    }
}

// Automatically move completed (checked) dashboard tasks to the bottom
function sortDashboardTasksInDOM() {
    const items = document.querySelectorAll('.task-item');
    if (!items.length) return;
    const container = items[0].parentElement;
    if (!container) return;

    const arr = Array.from(container.children).filter(child => child.classList.contains('task-item'));
    if (arr.length <= 1) return;

    arr.sort((a, b) => {
        const aChecked = a.querySelector('input[type="checkbox"]')?.checked ? 1 : 0;
        const bChecked = b.querySelector('input[type="checkbox"]')?.checked ? 1 : 0;
        return aChecked - bChecked;
    });

    arr.forEach(el => container.appendChild(el));
}

// AJAX Habit Day Toggle
async function toggleHabitDay(year, month, habitId, day, cellElement) {
    try {
        const response = await fetch('/api/monthly/habit/toggle', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ year, month, habit_id: habitId, day })
        });
        const data = await response.json();
        if (data.success) {
            if (data.checked) {
                cellElement.classList.remove('habit-cell-inactive');
                cellElement.classList.add('habit-cell-active');
                cellElement.innerText = day;
            } else {
                cellElement.classList.remove('habit-cell-active');
                cellElement.classList.add('habit-cell-inactive');
                cellElement.innerText = '•';
            }
        } else {
            console.error('Habit toggle failed:', data.message);
            showToast(data.message || 'Habit toggle failed', 'danger');
        }
    } catch (err) {
        console.error('Error toggling habit:', err);
    }
}

// Google Drive Backup Sync
async function syncToGoogleDrive() {
    try {
        const response = await fetch('/api/google/drive/sync', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        if (data.success) {
            showToast(data.message || 'Cloud Backup Complete! All planner data synced to Google Drive.', 'success');
        } else {
            showToast(data.message || 'Could not sync to Google Drive.', 'warning');
            if (data.google_connected === false) {
                setTimeout(() => {
                    if (confirm('Google Account is not connected. Would you like to download a local JSON backup file to your computer now?')) {
                        window.location.href = '/api/backup/export_json';
                    }
                }, 1000);
            }
        }
    } catch (err) {
        console.error('Drive sync error:', err);
        showToast('Could not sync to Google Drive. Please check your network connection.', 'danger');
    }
}

// Google Drive Data Restore
async function restoreFromGoogleDrive() {
    if (!confirm('Are you sure you want to restore your planner data from Google Drive? This will update your local records.')) {
        return;
    }
    try {
        const response = await fetch('/api/google/drive/restore', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        if (data.success) {
            showToast(data.message || 'Data restored successfully from Google Drive!', 'success');
            setTimeout(() => window.location.reload(), 1000);
        } else {
            showToast(data.message || 'Drive Restore failed.', 'danger');
        }
    } catch (err) {
        console.error('Drive restore error:', err);
        showToast('Could not restore from Google Drive.', 'danger');
    }
}

// Local JSON Backup Export
function takeLocalBackup() {
    showToast('Preparing full database backup JSON download...', 'info');
    window.location.href = '/api/backup/export_json';
}

// Local JSON Backup Restore
function triggerLocalRestoreFileSelect() {
    let input = document.getElementById('local-backup-file-input');
    if (!input) {
        input = document.createElement('input');
        input.type = 'file';
        input.id = 'local-backup-file-input';
        input.accept = '.json';
        input.className = 'hidden';
        input.onchange = function () { uploadLocalBackupFile(this); };
        document.body.appendChild(input);
    }
    input.value = '';
    input.click();
}

async function uploadLocalBackupFile(input) {
    if (!input.files || !input.files[0]) return;
    const file = input.files[0];
    if (!confirm(`Are you sure you want to restore database from "${file.name}"? This will update your planner tables.`)) {
        return;
    }

    const formData = new FormData();
    formData.append('backup_file', file);

    showToast('Restoring database tables from local backup...', 'info');
    try {
        const response = await fetch('/api/backup/restore_json', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        if (data.success) {
            showToast(data.message || 'Local backup restored successfully across all tables!', 'success');
            setTimeout(() => window.location.reload(), 1000);
        } else {
            showToast(data.message || 'Failed to restore local backup file.', 'danger');
        }
    } catch (err) {
        console.error('Local backup restore error:', err);
        showToast('Error uploading local backup file.', 'danger');
    }
}

// ==========================================
// Client-Side Tab Cache & Background Prefetch Architecture
// ==========================================

const TabCacheManager = {
    cache: new Map(),

    getKey(url) {
        try {
            const parsed = new URL(url, window.location.origin);
            let path = parsed.pathname;
            if (path.length > 1 && path.endsWith('/')) {
                path = path.slice(0, -1);
            }
            return path; // e.g. '/daily', '/weekly', '/monthly', '/yearly', '/dashboard', '/admin'
        } catch (e) {
            return url;
        }
    },

    get(url) {
        return this.cache.get(this.getKey(url));
    },

    set(url, html, title) {
        this.cache.set(this.getKey(url), {
            html,
            title,
            timestamp: Date.now()
        });
    },

    has(url) {
        return this.cache.has(this.getKey(url));
    },

    clear() {
        this.cache.clear();
    },

    invalidate(url) {
        this.cache.delete(this.getKey(url));
    }
};

// Re-execute scripts embedded inside newly injected main-content HTML
function executeContainerScripts(container) {
    if (!container) return;
    const scripts = container.querySelectorAll('script');
    scripts.forEach(oldScript => {
        const newScript = document.createElement('script');
        Array.from(oldScript.attributes).forEach(attr => newScript.setAttribute(attr.name, attr.value));
        newScript.textContent = oldScript.textContent;
        oldScript.parentNode.replaceChild(newScript, oldScript);
    });
}

// Dynamically update Desktop and Mobile Navigation Bar Tab Highlight Styles
function updateNavTabHighlight(targetUrl) {
    const targetKey = TabCacheManager.getKey(targetUrl);
    const navLinks = document.querySelectorAll('a[data-tab-link="true"]');

    navLinks.forEach(link => {
        const linkHref = link.getAttribute('href');
        const linkKey = TabCacheManager.getKey(linkHref);
        const isMatch = (linkKey === targetKey);
        const isAdminLink = linkKey === '/admin';

        if (isAdminLink) {
            if (isMatch) {
                link.classList.remove('text-amber-400', 'hover:bg-amber-500/10', 'hover:text-amber-300');
                if (!link.classList.contains('bg-amber-500')) {
                    link.classList.add('bg-amber-500', 'text-slate-950', 'font-bold', 'shadow-md', 'shadow-amber-500/20');
                }
            } else {
                link.classList.remove('bg-amber-500', 'text-slate-950', 'font-bold', 'shadow-md', 'shadow-amber-500/20', 'shadow-sm');
                if (!link.classList.contains('text-amber-400')) {
                    link.classList.add('text-amber-400', 'hover:bg-amber-500/10');
                }
            }
        } else {
            if (isMatch) {
                link.classList.remove('text-slate-300', 'hover:bg-slate-700/50', 'hover:bg-slate-700/60');
                if (!link.classList.contains('bg-brand-600')) {
                    link.classList.add('bg-brand-600', 'text-white', 'shadow-md', 'shadow-brand-500/20');
                }
            } else {
                link.classList.remove('bg-brand-600', 'text-white', 'shadow-md', 'shadow-brand-500/20', 'shadow-sm');
                if (!link.classList.contains('text-slate-300')) {
                    link.classList.add('text-slate-300', 'hover:bg-slate-700/50');
                }
            }
        }
    });
}

// Show/Hide Cold Load Top Progress Bar
function setTabLoadingProgress(show) {
    const bar = document.getElementById('tab-loading-progress');
    if (!bar) return;
    if (show) {
        bar.style.width = '70%';
        bar.classList.remove('opacity-0');
        bar.classList.add('opacity-100');
    } else {
        bar.style.width = '100%';
        setTimeout(() => {
            bar.classList.remove('opacity-100');
            bar.classList.add('opacity-0');
            setTimeout(() => { bar.style.width = '0%'; }, 300);
        }, 150);
    }
}

// Core Tab Switcher (Immediate rendering if cached, graceful fetch if missing)
async function switchTab(targetUrl, pushState = true) {
    const mainContent = document.getElementById('app-main-content');
    if (!mainContent) {
        window.location.href = targetUrl;
        return;
    }

    const key = TabCacheManager.getKey(targetUrl);

    // 1. CACHE HIT: Render immediately with zero delay & no loading spinner
    if (TabCacheManager.has(key)) {
        const cached = TabCacheManager.get(key);
        mainContent.innerHTML = cached.html;
        document.title = cached.title;
        updateNavTabHighlight(targetUrl);
        executeContainerScripts(mainContent);

        if (window.bindTaskDragEvents) {
            document.querySelectorAll('.task-card-wrapper').forEach(w => window.bindTaskDragEvents(w));
        }

        if (pushState && window.location.pathname !== key) {
            window.history.pushState({ path: targetUrl }, '', targetUrl);
        }
        window.scrollTo({ top: 0, behavior: 'smooth' });
        return;
    }

    // 2. CACHE MISS: Perform AJAX fetch with top loading bar
    setTabLoadingProgress(true);
    try {
        const response = await fetch(targetUrl, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });

        if (!response.ok) {
            window.location.href = targetUrl;
            return;
        }

        const htmlText = await response.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(htmlText, 'text/html');
        const newMain = doc.getElementById('app-main-content');
        const newTitle = doc.title || document.title;

        if (newMain) {
            const htmlContent = newMain.innerHTML;
            TabCacheManager.set(key, htmlContent, newTitle);

            mainContent.innerHTML = htmlContent;
            document.title = newTitle;
            updateNavTabHighlight(targetUrl);
            executeContainerScripts(mainContent);

            if (window.bindTaskDragEvents) {
                document.querySelectorAll('.task-card-wrapper').forEach(w => window.bindTaskDragEvents(w));
            }

            if (pushState && window.location.pathname !== key) {
                window.history.pushState({ path: targetUrl }, '', targetUrl);
            }
            window.scrollTo({ top: 0, behavior: 'smooth' });
        } else {
            window.location.href = targetUrl;
        }
    } catch (err) {
        console.error('Tab switch fetch error:', err);
        window.location.href = targetUrl;
    } finally {
        setTabLoadingProgress(false);
    }
}

// Background Prefetching of Un-cached Views (Daily, Weekly, Monthly, Yearly, Dashboard, Admin)
function prefetchRemainingViews() {
    const targetViews = ['/dashboard', '/daily', '/weekly', '/monthly', '/yearly', '/admin/'];
    const currentKey = TabCacheManager.getKey(window.location.pathname);

    // Cache initial view if present
    const mainContent = document.getElementById('app-main-content');
    if (mainContent && !TabCacheManager.has(currentKey)) {
        TabCacheManager.set(currentKey, mainContent.innerHTML, document.title);
    }

    targetViews.forEach(route => {
        if (!TabCacheManager.has(route)) {
            fetch(route, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
                .then(res => res.ok ? res.text() : null)
                .then(htmlText => {
                    if (!htmlText) return;
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(htmlText, 'text/html');
                    const newMain = doc.getElementById('app-main-content');
                    const newTitle = doc.title || document.title;
                    if (newMain) {
                        TabCacheManager.set(route, newMain.innerHTML, newTitle);
                    }
                })
                .catch(err => {
                    console.warn(`[Background Prefetch] Could not prefetch ${route}:`, err);
                });
        }
    });
}

// Seamless AJAX Content Refreshing without full browser page reload
async function refreshMainContentAsync() {
    try {
        const currentUrl = window.location.href;
        const response = await fetch(currentUrl, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        const htmlText = await response.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(htmlText, 'text/html');
        const newContent = doc.getElementById('app-main-content');
        const currentContent = document.getElementById('app-main-content');
        if (newContent && currentContent) {
            currentContent.innerHTML = newContent.innerHTML;

            // Invalidate/update cache entry for current route so cache stays fresh
            TabCacheManager.set(currentUrl, newContent.innerHTML, doc.title || document.title);

            executeContainerScripts(currentContent);
            if (window.bindTaskDragEvents) {
                document.querySelectorAll('.task-card-wrapper').forEach(wrapper => {
                    window.bindTaskDragEvents(wrapper);
                });
            }
        }
    } catch (err) {
        console.error('Async main content refresh error:', err);
    }
}

// Global Interceptor for Tab Clicks & Form Submissions
document.addEventListener('DOMContentLoaded', () => {
    // Auto-dismiss floating alerts after 6 seconds
    const alerts = document.querySelectorAll('.flash-alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            dismissAlert(alert);
        }, 6000);
    });

    // Populate initial cache & start background prefetching
    prefetchRemainingViews();
});

// Global Click Delegation for Tab Switching
document.addEventListener('click', (e) => {
    const link = e.target.closest('a');
    if (!link) return;

    const isTabLink = link.getAttribute('data-tab-link') === 'true';
    const href = link.getAttribute('href');

    if (isTabLink && href && !href.startsWith('#') && !href.startsWith('javascript:')) {
        e.preventDefault();
        switchTab(href, true);
        return;
    }

    // Intercept standard internal links for tab routes (/dashboard, /daily, /weekly, /monthly, /yearly, /admin, /admin/)
    if (href && (href === '/dashboard' || href === '/daily' || href === '/weekly' || href === '/monthly' || href === '/yearly' || href === '/admin' || href === '/admin/')) {
        e.preventDefault();
        switchTab(href, true);
    }
});

// Browser History Back/Forward Navigation Handler
window.addEventListener('popstate', (e) => {
    switchTab(window.location.href, false);
});

// Global Interceptor for POST forms across planners
document.addEventListener('submit', async (e) => {
    if (e.defaultPrevented) return;
    const form = e.target;
    if (!form || !form.method || form.method.toUpperCase() !== 'POST') return;
    if (form.getAttribute('data-no-ajax') === 'true') return;

    const actionUrl = form.action || window.location.href;
    if (actionUrl.includes('/auth/') || actionUrl.includes('/admin/') || actionUrl.includes('/api/backup/restore_json')) return;
    if (form.querySelector('input[type="file"]')) return;

    e.preventDefault();
    const formData = new FormData(form);
    formData.append('is_ajax', 'true');

    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) submitBtn.disabled = true;

    try {
        const response = await fetch(actionUrl, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: formData
        });

        let data = {};
        try {
            data = await response.json();
        } catch (jsonErr) {
            data = { success: true };
        }

        if (data.success) {
            // Close open modal containers if any
            const modalElems = document.querySelectorAll('dialog[open], #edit-task-modal:not(.hidden), #depression-modal:not(.hidden), #memory-modal:not(.hidden), #add-item-modal:not(.hidden)');
            modalElems.forEach(m => {
                if (m.tagName && m.tagName.toLowerCase() === 'dialog') {
                    m.close();
                } else {
                    m.classList.add('hidden');
                }
            });

            // Invalidate other cached tab views so they re-fetch fresh data on next visit
            TabCacheManager.clear();

            await refreshMainContentAsync();
            if (data.message) {
                showToast(data.message, 'success');
            }
        } else {
            showToast(data.message || 'Operation failed', 'danger');
        }
    } catch (err) {
        console.error('Global AJAX submit error:', err);
        showToast('Server error executing request', 'danger');
    } finally {
        if (submitBtn) submitBtn.disabled = false;
    }
});



