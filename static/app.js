document.addEventListener('DOMContentLoaded', () => {
    // Check API Status
    fetch('/api/status')
        .then(res => res.json())
        .then(data => {
            const indicator = document.querySelector('.status-indicator');
            const text = document.getElementById('api-status-text');
            if (data.api_keys_configured) {
                indicator.classList.add('online');
                text.textContent = 'Systems Online';
            } else {
                indicator.classList.add('offline');
                text.textContent = 'API Keys Missing!';
            }
        }).catch(err => {
            document.querySelector('.status-indicator').classList.add('offline');
            document.getElementById('api-status-text').textContent = 'Backend Offline';
        });

    // Tab Navigation
    const navItems = document.querySelectorAll('.nav-item');
    const viewSections = document.querySelectorAll('.view-section');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const target = e.currentTarget.getAttribute('data-tab');
            
            navItems.forEach(n => n.classList.remove('active'));
            e.currentTarget.classList.add('active');
            
            viewSections.forEach(section => {
                if (section.id === `${target}-view`) {
                    section.classList.add('active');
                } else {
                    section.classList.remove('active');
                }
            });

            if (target === 'dashboard') {
                loadDashboard();
            }
        });
    });

    // Dashboard Data Loading
    function loadDashboard() {
        document.getElementById('loading-team').classList.remove('hidden');
        document.getElementById('starting-xi-list').innerHTML = '';
        document.getElementById('subs-list').innerHTML = '';

        fetch('/api/team?team=default')
            .then(res => res.json())
            .then(data => {
                document.getElementById('loading-team').classList.add('hidden');
                
                if (data.error || !data.team) {
                    document.getElementById('loading-team').innerHTML = '<p>No team data found.</p>';
                    document.getElementById('login-overlay').style.display = 'block';
                    return;
                } else {
                    document.getElementById('login-overlay').style.display = 'none';
                }

                const team = data.team.team || data.team;
                
                document.getElementById('team-value').textContent = `£${team.total_cost || 0}m`;
                document.getElementById('team-bank').textContent = `£${team.bank || 0}m`;
                document.getElementById('team-xpts').textContent = team.expected_points || 0;
                document.getElementById('team-chip').textContent = team.chip ? team.chip.toUpperCase() : 'None';
                
                document.getElementById('cap-name').textContent = team.captain || '-';
                document.getElementById('vice-name').textContent = team.vice_captain || '-';

                // Render Starters
                const startingList = document.getElementById('starting-xi-list');
                if (team.starting) {
                    team.starting.forEach(p => {
                        startingList.innerHTML += createPlayerCard(p);
                    });
                }

                // Render Subs
                const subsList = document.getElementById('subs-list');
                if (team.substitutes) {
                    team.substitutes.forEach(p => {
                        subsList.innerHTML += createPlayerCard(p);
                    });
                }
            })
            .catch(err => {
                document.getElementById('loading-team').innerHTML = '<p>Error loading team.</p>';
            });
    }

    function createPlayerCard(player) {
        return `
            <div class="player-item">
                <div class="p-info">
                    <h4>${player.name}</h4>
                    <p>${player.position} | ${player.team}</p>
                </div>
                <div class="p-price">£${player.price}m</div>
            </div>
        `;
    }

    // Load initial dashboard
    loadDashboard();

    // Login Handler
    document.getElementById('btn-login')?.addEventListener('click', () => {
        const teamId = document.getElementById('login-team-id').value;
        
        if (!teamId) {
            alert('Please enter your Team ID');
            return;
        }

        document.getElementById('login-loader').classList.remove('hidden');
        document.getElementById('btn-login').disabled = true;

        fetch('/api/import_team', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ team_id: parseInt(teamId) })
        })
        .then(res => res.json())
        .then(data => {
            document.getElementById('login-loader').classList.add('hidden');
            document.getElementById('btn-login').disabled = false;
            
            if(data.success) {
                document.getElementById('login-overlay').style.display = 'none';
                loadDashboard();
            } else {
                alert('Import failed: ' + data.error);
            }
        });
    });

    // Update Team
    document.getElementById('btn-update').addEventListener('click', () => {
        const autoSync = document.getElementById('sync-checkbox').checked;
        const email = document.getElementById('fpl-email').value;
        const password = document.getElementById('fpl-password').value;

        document.getElementById('update-loader').classList.remove('hidden');
        document.getElementById('update-result').classList.add('hidden');
        document.getElementById('btn-update').disabled = true;

        fetch('/api/update', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ 
                team: 'default', 
                auto_sync: autoSync,
                email: email,
                password: password
            })
        })
        .then(res => res.json())
        .then(data => {
            document.getElementById('update-loader').classList.add('hidden');
            document.getElementById('btn-update').disabled = false;
            const resBox = document.getElementById('update-result');
            resBox.classList.remove('hidden');

            if(data.success) {
                const ai = data.team?.team || {};
                
                let transferHtml = '';
                if (ai.transfers && ai.transfers.length > 0) {
                    transferHtml = '<h4>Transfers</h4><ul>' + ai.transfers.map(t => 
                        `<li>🔴 Out: ${t.player_out} (£${t.player_out_price}m) <br/> 🟢 In: ${t.player_in} (£${t.player_in_price}m) <br/> <span style="opacity: 0.8; font-size: 0.9em;">Reason: ${t.reason}</span></li>`
                    ).join('') + '</ul>';
                } else {
                    transferHtml = '<p>No transfers recommended this week.</p>';
                }

                let chipHtml = '';
                if (ai.chip && ai.chip.toLowerCase() !== 'none') {
                    chipHtml = `<h4>Chip Strategy: ${ai.chip.toUpperCase()}</h4><p><span style="opacity: 0.8; font-size: 0.9em;">${ai.chip_reason}</span></p>`;
                }
                
                let capHtml = '';
                if (ai.captain) {
                    capHtml = `<h4>Captaincy</h4><p><strong>C:</strong> ${ai.captain} <br/><span style="opacity: 0.8; font-size: 0.9em;">(${ai.captain_reason})</span></p><p><strong>VC:</strong> ${ai.vice_captain} <br/><span style="opacity: 0.8; font-size: 0.9em;">(${ai.vice_captain_reason})</span></p>`;
                }

                resBox.innerHTML = `
                    <h3>✅ AI Analysis Complete</h3>
                    <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; margin-top: 15px; margin-bottom: 15px; text-align: left;">
                        ${chipHtml}
                        ${transferHtml}
                        ${capHtml}
                    </div>
                    <button class="btn-secondary" style="margin-top:1rem; width: 100%;" onclick="document.querySelector('[data-tab=\\'dashboard\\']').click()">View New Squad</button>
                `;
            } else {
                resBox.innerHTML = `<h3>❌ Error</h3><p>${data.error}</p>`;
            }
        });
    });
});
