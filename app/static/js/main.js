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
        input.onchange = function() { uploadLocalBackupFile(this); };
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

// Seamless AJAX Content Refreshing without full browser page reload
async function refreshMainContentAsync() {
    try {
        const response = await fetch(window.location.href, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        const htmlText = await response.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(htmlText, 'text/html');
        const newContent = doc.getElementById('app-main-content');
        const currentContent = document.getElementById('app-main-content');
        if (newContent && currentContent) {
            currentContent.innerHTML = newContent.innerHTML;
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

// Global Interceptor for POST forms across planners
document.addEventListener('submit', async (e) => {
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



