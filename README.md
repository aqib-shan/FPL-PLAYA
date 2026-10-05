# FPL Agent - AI-Powered Fantasy Premier League Manager

FPL Agent is my experiment in getting AI to manage my FPL team - building squads, firing off transfers and chips, and competing over a season while a custom RAG pipeline feeds them fixtures, player data and context each gameweek. For a detailed explanation please see the [project page](https://www.abeard.ai/projects/fpl-arena).

### Using FPL Agent to Build a Team

*A sample of a team from Grok-4 for Gameweek 26 of the 2025/26 PL season.*

**Captain:** Viktor Gyökeres ("due to his double gameweek with Arsenal facing Brentford and Wolves, providing two opportunities for points. As Arsenal's primary goal threat with a PPG of 3.7, 8 goals, and expert insights labeling him a must-have...")

**Vice Captain:** Cole Palmer ("for his exceptional form with a PPG of 8.6, 8 goals, and 2 assists, making him Chelsea's talisman. With a favorable home fixture against Leeds, expert insights mark him as a must-have, and community tips highlight his consistency in delivering points...")

**GK:** Jordan Pickford ("selected for the starting 11 due to his consistent performances with a PPG of 3.6, 9 clean sheets, and high save potential (71 saves). Everton's home fixture against Bournemouth offers good clean sheet odds...")

**DEF:** Gabriel dos Santos Magalhães ("for his double gameweek potential, with Arsenal's strong defense (13 clean sheets overall) and his personal stats (PPG 4.3, 18 bonus points). Expert tips from FPL Scout and Reddit emphasize him as a top Arsenal pick for DGW26 due to set-piece threat...")

**DEF:** Ladislav Krejčí ("for his double gameweek against Nott'm Forest and Arsenal, offering value at £4.5m with consistent minutes (1707) and some attacking returns. Research from RotoWire and FPL Geek recommends Wolves defenders for DGW, noting his regular starts and potential for clean sheets...")

...

## 🎯 What This Project Does

FPL Agent powers automated FPL team management and the FPL Arena competition, combining live FPL data with LLM-driven analysis to build and update teams throughout the season.

- **Automated FPL decisions**: Team creation, weekly transfers, captaincy and chip suggestions
- **Custom RAG pipeline**: Structured prompts with fixtures, squad context and complex FPL rules
- **Player enrichment**: Gemini 2.5 Flash-Lite classifies player hints/tips and availability using stats and web search
- **Multi-model experiments**: Run different LLMs/strategies and compare their performance in a shared dashboard

## 📦 Installation

### Prerequisites
- Python 3.11+
- pip

### Setup

1. **Clone the repository**
```bash
git clone <repository-url>
cd fpl-agent
```

2. **Create and activate virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Environment Configuration**
Copy `.env.example` to `.env` and add your API keys (or create a `.env` file in the project root):
```env
# Gemini AI API Key (can be used for default Gemini models, subject to limits)
GEMINI_API_KEY=your_gemini_api_key_here

# OpenRouter API Key (to tap into any model via Openrouter)
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

**Note**: You need at least one of these API keys depending on which models you configure in `fpl_agent/config.yaml`.

5. **Configuration**
Edit `fpl_agent/config.yaml` to customize:
- LLM model settings
- Team composition rules
- Embedding configuration
- Display preferences

## 🎮 Usage

### Command Line Interface

The FPL Agent provides a CLI with the following main commands:

#### Data Management
```bash
# Fetch fresh FPL data
fpl-agent fetch

# Fetch with enrichments (expert insights + injury news)
fpl-agent fetch --use-enrichments

# Use cached data only
fpl-agent fetch --cached-only

# Enrich existing data with AI insights
fpl-agent enrich

# Show data status
fpl-agent show-data

# Show available players breakdown
fpl-agent show-players
```

#### Team Management
```bash
# Create a new team
fpl-agent build-team --team "My Team" --budget 100.0

# Create team for specific gameweek
fpl-agent build-team --team "My Team" --budget 100.0 --gameweek 15

# Create team using different RAG modes
fpl-agent build-team --team "My Team" --rag-mode none  # No LLM player enrichments
fpl-agent build-team --team "My Team" --rag-mode enrichments  # Basic LLM player enrichments
fpl-agent build-team --team "My Team" --rag-mode ranked_enrichments  # Full LLM player enrichments

# Save team to file
fpl-agent build-team --team "My Team" --save-team
```

#### Example

This is an example JSON payload for a `Grok-4` team built for Gameweek 26 (as stored under `team_data/Grok-4/gw26.json`).

Team Building:

```
fpl-agent build-team --gameweek 26 --team Grok-4 --save-team
```

Result:

```json
{
  "team": {
    "captain": "Viktor Gyökeres",
    "vice_captain": "Cole Palmer",
    "captain_reason": "Viktor Gyökeres is selected as captain due to his double gameweek with Arsenal facing Brentford and Wolves, providing two opportunities for points. As Arsenal's primary goal threat with a PPG of 3.7, 8 goals, and expert insights labeling him a must-have for the DGW, he offers high expected returns based on Arsenal's strong defensive record and attacking form. Research from FPL sources emphasizes tripling up on Arsenal for GW26, and his fixtures are favorable for goals against mid-table opposition.",
    "vice_captain_reason": "Cole Palmer is chosen as vice-captain for his exceptional form with a PPG of 8.6, 8 goals, and 2 assists, making him Chelsea's talisman. With a favorable home fixture against Leeds, expert insights mark him as a must-have, and community tips highlight his consistency in delivering points through goals, assists, and bonuses, providing reliability if the captain underperforms.",
    "total_cost": 99.4,
    "bank": 0.1,
    "expected_points": 70.0,
    "starting": [
      {
        "name": "Jordan Pickford",
        "position": "GK",
        "price": 5.6,
        "team": "Everton",
        "reason": "Pickford is selected for the starting 11 due to his consistent performances with a PPG of 3.6, 9 clean sheets, and high save potential (71 saves). Everton's home fixture against Bournemouth offers good clean sheet odds, and expert recommendations highlight him as a reliable budget option with minimal rotation risk, backed by fixture difficulty analysis showing a favorable matchup."
      },
      {
        "name": "Gabriel dos Santos Magalhães",
        "position": "DEF",
        "price": 7.1,
        "team": "Arsenal",
        "reason": "Gabriel is in the starting 11 for his double gameweek potential, with Arsenal's strong defense (13 clean sheets overall) and his personal stats (PPG 4.3, 18 bonus points). Expert tips from FPL Scout and Reddit emphasize him as a top Arsenal pick for DGW26 due to set-piece threat and clean sheet likelihood against Brentford and Wolves, with low injury risk and high ownership reflecting community consensus."
      },
      {
        "name": "Ladislav Krejčí",
        "position": "DEF",
        "price": 4.5,
        "team": "Wolves",
        "reason": "Krejčí is started for his double gameweek against Nott'm Forest and Arsenal, offering value at £4.5m with consistent minutes (1707) and some attacking returns. Research from RotoWire and FPL Geek recommends Wolves defenders for DGW, noting his regular starts and potential for clean sheets or bonuses, despite tougher fixtures, as a budget enabler with good underlying stats."
      },
      {
        "name": "Marc Guéhi",
        "position": "DEF",
        "price": 5.2,
        "team": "Man City",
        "reason": "Guéhi is selected for starting due to Man City's favorable home fixture against Fulham, with high clean sheet potential (9 clean sheets). His PPG of 3.8, bonus points (9), and expert insights from blogs highlight defensive solidity and value, with pre-season form and low rotation risk making him ideal for this gameweek's points accumulation."
      },
      {
        "name": "Declan Rice",
        "position": "MID",
        "price": 7.6,
        "team": "Arsenal",
        "reason": "Rice starts for his double gameweek role in Arsenal's midfield, contributing 4 goals and 7 assists with a PPG of 2.7. FPL tips from Premier League and Fantasy Football Hub strongly recommend him as part of the Arsenal triple-up for GW26, citing his clean sheet bonuses, occasional attacking returns, and reliability as a starter with no injury concerns."
      },
      {
        "name": "João Victor Gomes da Silva",
        "position": "MID",
        "price": 5.3,
        "team": "Wolves",
        "reason": "Gomes is in the starting lineup for his double gameweek, as a nailed-on starter (2024 minutes) with defensive contributions and potential bonuses. Expert predictions from RotoWire and YouTube previews highlight him as a smart DGW pick for Wolves, offering value at £5.3m with consistent points from tackles and interceptions, despite Wolves' form."
      },
      {
        "name": "Cole Palmer",
        "position": "MID",
        "price": 10.6,
        "team": "Chelsea",
        "reason": "Palmer is started due to his outstanding form (PPG 8.6, 8 goals, 2 assists) and Chelsea's easy home fixture against Leeds. Community forums and expert blogs label him a must-have with high ownership (14.9%), set-piece duties, and proven FPL returns, minimizing rotation risk and maximizing points potential for GW26 and beyond."
      },
      {
        "name": "Phil Foden",
        "position": "MID",
        "price": 8.2,
        "team": "Man City",
        "reason": "Foden is selected for starting given Man City's attacking fixture against Fulham, his form (7 goals, 3 assists), and must-have status per expert insights. With high ICT (160.3) and bonus potential, research from FPL sources recommends him for consistent returns, low injury risk, and strong upcoming fixtures."
      },
      {
        "name": "Bruno Borges Fernandes",
        "position": "MID",
        "price": 9.8,
        "team": "Man Utd",
        "reason": "Bruno starts for his elite PPG (7.4), 6 goals, and 12 assists, making him Man Utd's key creator against West Ham. Expert recommendations emphasize his bonus points (25) and penalty duties, with community analysis showing reliability despite the away fixture, and no international absences affecting him."
      },
      {
        "name": "Viktor Gyökeres",
        "position": "FWD",
        "price": 8.8,
        "team": "Arsenal",
        "reason": "Gyökeres is in the starting 11 for his double gameweek, with 8 goals and high expected minutes. As a must-have per expert insights and FPL previews, his form and Arsenal's attacking strength against Brentford and Wolves provide excellent goal potential, supported by statistical analysis and low rotation risk."
      },
      {
        "name": "João Pedro Junqueira de Jesus",
        "position": "FWD",
        "price": 7.7,
        "team": "Chelsea",
        "reason": "João Pedro starts due to his impressive PPG (9.6), 10 goals, and 8 assists, with Chelsea's favorable fixture against Leeds. Expert tips highlight him as a must-have talisman with set-piece involvement and consistent returns, backed by fixture difficulty ratings and community discussions for optimal value."
      }
    ],
    "substitutes": [
      {
        "name": "Mateus Mané",
        "position": "FWD",
        "price": 4.6,
        "team": "Wolves",
        "sub_order": 1,
        "reason": "Mané is on the bench as a budget DGW option with potential for goals (2) and assists (2), prioritized as first sub due to his double fixtures providing upside if a starter fails to play. Expert differentials from Never Manage Alone recommend him for low-ownership value, useful in case of rotation or injury in attack."
      },
      {
        "name": "Micky van de Ven",
        "position": "DEF",
        "price": 4.5,
        "team": "Spurs",
        "sub_order": 2,
        "reason": "Van de Ven is benched for squad depth, offering clean sheet potential (7) and bonus points (10) in Spurs' home game against Newcastle. As second sub, his priority reflects decent expected points if needed, based on expert analysis favoring him for value and minimal risk, ideal for defensive substitutions."
      },
      {
        "name": "James Tarkowski",
        "position": "DEF",
        "price": 5.7,
        "team": "Everton",
        "sub_order": 3,
        "reason": "Tarkowski is on the bench for his consistent starts and clean sheet contributions (9), with Everton's home fixture against Bournemouth. Ranked third sub due to lower upside compared to DGW players, but useful for defensive cover, as per community insights on his bonus potential and reliability."
      },
      {
        "name": "Mads Hermansen",
        "position": "GK",
        "price": 4.2,
        "team": "West Ham",
        "sub_order": null,
        "reason": "Hermansen is selected as backup goalkeeper for his low price and solid underlying stats (PPG 2.4, saves), providing cost-effective cover without rotation risk. Expert recommendations note him as a strong budget option, ensuring squad compliance while freeing budget for premiums."
      }
    ]
  }
}
```

#### Weekly Updates
```bash
# Get weekly recommendations for a team
fpl-agent gw-update --team "My Team"

# Update for specific gameweek
fpl-agent gw-update --team "My Team" --gameweek 15

# Update using cached data only
fpl-agent gw-update --team "My Team" --cached-only

# Save weekly update
fpl-agent gw-update --team "My Team" --save-team
```

#### Multi-Team Operations
```bash
# List all teams
fpl-agent list-teams

# Show specific team
fpl-agent show-team --team "My Team"

# Show all teams
fpl-agent show-team --all-teams

# Delete a team
fpl-agent delete-team --team "My Team"

# Run operations on all teams
fpl-agent build-team --all-teams --budget 100.0
fpl-agent gw-update --all-teams
```

#### Debug and Development
```bash
# Show debug information
fpl-agent fetch --debug

# Show verbose logging
fpl-agent fetch --verbose

# Show LLM prompts (for debugging)
fpl-agent build-team --team "My Team" --show-prompt
fpl-agent gw-update --team "My Team" --show-prompt
```

## 🔧 Configuration

### LLM Settings (`config.yaml`)

```yaml
llm:
  main:
    model: "gemini-2.5-pro"  # Primary model for complex tasks
    max_output_tokens: 65536
    temperature: 0.3
    max_retries: 1
  
  lightweight:
    model: "gemini-2.5-flash-lite"  # Cost-effective for analysis
    max_output_tokens: 16384
    temperature: 0.2
    max_retries: 3
```

### Team Configuration

```yaml
team:
  squad_size: 15
  position_limits:
    GK: 2
    DEF: 5
    MID: 5
    FWD: 3
  budget: 100.0
  max_players_per_team: 3
```

### Embedding Configuration

```yaml
embeddings:
  use_embeddings: true
  model: "BAAI/bge-base-en-v1.5"
  cache_enabled: true
  cache_expiry_hours: 24
  batch_size: 100
```

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing
If you'd like to contribute to this, please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📞 Support

For issues, feature requests, or questions:
- Open an issue on GitHub
- Check existing issues for solutions
- Review configuration options in `config.yaml`
