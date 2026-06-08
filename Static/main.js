function selectTab(tabName) {
    document.querySelectorAll('.hod-nav-button').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });
    document.querySelectorAll('.hod-panel').forEach(panel => {
        panel.classList.toggle('hidden', panel.id !== tabName);
    });
}

function formatText(text) {
    return text ? text : '—';
}

function renderStats(state) {
    document.getElementById('stat-new').textContent = state.stats.new;
    document.getElementById('stat-assigned').textContent = state.stats.assigned;
    document.getElementById('stat-completed').textContent = state.stats.completed;
    document.getElementById('stat-total-active').textContent = state.stats.totalActive;
}

function renderEnquiries(state) {
    const tbody = document.getElementById('enquiries-tbody');
    tbody.innerHTML = '';

    if (!state.enquiries.length) {
        const tr = document.createElement('tr');
        tr.innerHTML = '<td colspan="7" class="hod-empty-state">No enquiries found.</td>';
        tbody.appendChild(tr);
        return;
    }

    state.enquiries.forEach(enquiry => {
        const tr = document.createElement('tr');
        const assignCell = document.createElement('td');
        assignCell.className = 'hod-assign-cell';

        if (enquiry.assigned_dpo_id) {
            assignCell.textContent = enquiry.assigned_dpo_name || 'Assigned';
        } else if (!state.availableDpos.length) {
            assignCell.textContent = 'No DPO available';
        } else {
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = '/assign_dpo';
            form.className = 'hod-assign-form';

            const hiddenInput = document.createElement('input');
            hiddenInput.type = 'hidden';
            hiddenInput.name = 'enquiry_id';
            hiddenInput.value = enquiry.id;
            form.appendChild(hiddenInput);

            const select = document.createElement('select');
            select.name = 'dpo_id';
            select.required = true;
            state.availableDpos.forEach(dpo => {
                const option = document.createElement('option');
                option.value = dpo.id;
                option.textContent = `${dpo.name} (${dpo.activeCount} active)`;
                select.appendChild(option);
            });
            form.appendChild(select);

            const button = document.createElement('button');
            button.type = 'submit';
            button.textContent = 'Assign';
            form.appendChild(button);

            assignCell.appendChild(form);
        }

        tr.innerHTML = `
            <td>${enquiry.id}</td>
            <td>${formatText(enquiry.enquirer_name)}<br><span class="hod-small-text">${formatText(enquiry.enquirer_email)}</span></td>
            <td>${formatText(enquiry.title)}</td>
            <td>${formatText(enquiry.description)}</td>
            <td>${formatText(enquiry.deadline)}</td>
            <td>${formatText(enquiry.status)}</td>
        `;
        tr.appendChild(assignCell);
        tbody.appendChild(tr);
    });
}

function renderWorkload(state) {
    const container = document.getElementById('dpo-workload-list');
    container.innerHTML = '';

    if (!state.dpoWorkloads.length) {
        container.innerHTML = '<div class="hod-empty-state">No DPOs are configured.</div>';
        return;
    }

    state.dpoWorkloads.forEach(dpo => {
        const card = document.createElement('article');
        card.className = 'hod-workload-card';
        card.innerHTML = `
            <div class="hod-workload-card-header">
                <div>
                    <h3>${dpo.name}</h3>
                    <p class="hod-small-text">${dpo.email}</p>
                </div>
                <span class="hod-badge ${dpo.statusBadgeClass}">${dpo.statusBadgeText}</span>
            </div>
            <div class="hod-workload-meta">
                <strong>${dpo.activeCount}</strong> active enquiries
            </div>
            <div class="hod-workload-list-items">
                ${dpo.assignedTitles.length ? dpo.assignedTitles.map((title, index) => `<p><strong>#${dpo.assignedEnquiryIds[index]}:</strong> ${title}</p>`).join('') : '<p class="hod-small-text">No active assignments.</p>'}
            </div>
        `;
        container.appendChild(card);
    });
}

function renderProfile(state) {
    document.getElementById('profile-name').textContent = state.profile.name || '—';
    document.getElementById('profile-email').textContent = state.profile.email || '—';
    document.getElementById('hod-name').value = state.profile.name || '';
    document.getElementById('hod-email').value = state.profile.email || '';
}

window.addEventListener('DOMContentLoaded', () => {
    const state = window.__HOD_STATE__ || {
        stats: { new: 0, assigned: 0, completed: 0, totalActive: 0 },
        enquiries: [],
        dpoWorkloads: [],
        availableDpos: [],
        profile: { name: '', email: '' }
    };

    renderStats(state);
    renderEnquiries(state);
    renderWorkload(state);
    renderProfile(state);

    document.querySelectorAll('.hod-nav-button').forEach(button => {
        button.addEventListener('click', () => {
            selectTab(button.dataset.tab);
        });
    });
});