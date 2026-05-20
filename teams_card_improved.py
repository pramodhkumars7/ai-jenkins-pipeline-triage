"""
Enhanced Teams Adaptive Card for Pipeline Triage
Makes notifications readable, scannable, and actionable
"""
import re


def parse_rca(rca_text):
    """
    Parse RCA text into structured sections
    Returns: dict with 'cause', 'fix', 'confidence', 'steps'
    """
    sections = {
        'cause': '',
        'fix': '',
        'confidence': 'Medium',
        'steps': []
    }

    lines = rca_text.split('\n')
    current_section = None

    for line in lines:
        line_lower = line.lower().strip()

        # Detect sections
        if 'root cause' in line_lower or 'what went wrong' in line_lower:
            current_section = 'cause'
            continue
        elif 'recommended fix' in line_lower or 'solution' in line_lower or 'how to fix' in line_lower:
            current_section = 'fix'
            continue
        elif 'confidence' in line_lower:
            # Extract confidence level
            for level in ['high', 'medium', 'low']:
                if level in line_lower:
                    sections['confidence'] = level.capitalize()
            continue

        # Extract numbered steps (1. 2. 3. etc)
        if re.match(r'^\d+\.', line.strip()):
            sections['steps'].append(line.strip())
            continue

        # Add to current section
        if current_section and line.strip():
            if sections[current_section]:
                sections[current_section] += '\n' + line
            else:
                sections[current_section] = line

    # Clean up sections
    for key in ['cause', 'fix']:
        sections[key] = sections[key].strip()

    return sections


def truncate_smart(text, max_length=400):
    """
    Intelligently truncate text while preserving meaning
    """
    if len(text) <= max_length:
        return text

    # Try to cut at sentence boundary
    truncated = text[:max_length]
    last_period = truncated.rfind('.')
    last_newline = truncated.rfind('\n')

    cut_point = max(last_period, last_newline)
    if cut_point > max_length * 0.7:  # Only use if we keep >70%
        return truncated[:cut_point + 1] + " [...]"

    return truncated + "..."


def get_severity_color(error_class):
    """
    Map error type to color for visual emphasis
    """
    critical_errors = ['OOMKilled', 'CrashLoopBackOff', 'AssertionError']
    warning_errors = ['TimeoutError', 'ReadinessProbeFailed']

    if error_class in critical_errors:
        return 'Attention'  # Red
    elif error_class in warning_errors:
        return 'Warning'    # Yellow
    else:
        return 'Default'    # Gray


def get_priority_emoji(confidence):
    """
    Visual indicator for confidence/priority
    """
    if confidence == 'High':
        return '🔴'  # High priority
    elif confidence == 'Medium':
        return '🟡'  # Medium priority
    else:
        return '🟢'  # Low priority


def create_enhanced_teams_card(job, branch, category, error_class, rca, pr_url, actions_url, commit="unknown"):
    """
    Create a beautiful, readable Teams adaptive card
    """
    # Parse RCA into sections
    sections = parse_rca(rca)
    severity_color = get_severity_color(error_class)
    priority_emoji = get_priority_emoji(sections['confidence'])

    # Build the card
    card = {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.5",
                "body": [
                    # ─── HEADER ───
                    {
                        "type": "Container",
                        "style": "emphasis",
                        "items": [
                            {
                                "type": "ColumnSet",
                                "columns": [
                                    {
                                        "type": "Column",
                                        "width": "auto",
                                        "items": [{
                                            "type": "Image",
                                            "url": "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png",
                                            "size": "Small",
                                            "width": "32px"
                                        }]
                                    },
                                    {
                                        "type": "Column",
                                        "width": "stretch",
                                        "items": [
                                            {
                                                "type": "TextBlock",
                                                "text": "❌ Pipeline Failure Detected",
                                                "weight": "Bolder",
                                                "size": "Large",
                                                "color": severity_color,
                                            },
                                            {
                                                "type": "TextBlock",
                                                "text": f"{job}",
                                                "size": "Small",
                                                "color": "Default",
                                                "spacing": "None",
                                            }
                                        ]
                                    },
                                    {
                                        "type": "Column",
                                        "width": "auto",
                                        "items": [{
                                            "type": "TextBlock",
                                            "text": priority_emoji,
                                            "size": "ExtraLarge",
                                            "horizontalAlignment": "Right",
                                        }]
                                    }
                                ]
                            }
                        ]
                    },

                    # ─── QUICK FACTS ───
                    {
                        "type": "Container",
                        "separator": True,
                        "spacing": "Medium",
                        "items": [
                            {
                                "type": "FactSet",
                                "facts": [
                                    {"title": "🌿 Branch", "value": branch[:50]},
                                    {"title": "📦 Category", "value": category},
                                    {"title": "⚠️ Error Type", "value": error_class},
                                    {"title": "🎯 Confidence", "value": f"{sections['confidence']} {priority_emoji}"},
                                ]
                            }
                        ]
                    },

                    # ─── ROOT CAUSE ───
                    {
                        "type": "Container",
                        "separator": True,
                        "spacing": "Medium",
                        "style": "accent",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": "🔍 Root Cause",
                                "weight": "Bolder",
                                "size": "Medium",
                            },
                            {
                                "type": "TextBlock",
                                "text": truncate_smart(sections['cause'], 350) if sections['cause'] else "Analyzing...",
                                "wrap": True,
                                "spacing": "Small",
                                "color": "Default",
                            }
                        ]
                    },

                    # ─── RECOMMENDED FIX ───
                    {
                        "type": "Container",
                        "separator": True,
                        "spacing": "Medium",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": "💡 Recommended Fix",
                                "weight": "Bolder",
                                "size": "Medium",
                            },
                            {
                                "type": "TextBlock",
                                "text": truncate_smart(sections['fix'], 350) if sections['fix'] else "See PR for details",
                                "wrap": True,
                                "spacing": "Small",
                            }
                        ]
                    },

                    # ─── ACTION STEPS (if available) ───
                    *([{
                        "type": "Container",
                        "separator": True,
                        "spacing": "Medium",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": "📋 Action Steps",
                                "weight": "Bolder",
                                "size": "Medium",
                            },
                            *[{
                                "type": "TextBlock",
                                "text": step,
                                "wrap": True,
                                "spacing": "Small",
                            } for step in sections['steps'][:3]]  # Max 3 steps
                        ]
                    }] if sections['steps'] else []),

                    # ─── STATUS FOOTER ───
                    {
                        "type": "Container",
                        "separator": True,
                        "spacing": "Medium",
                        "items": [
                            {
                                "type": "ColumnSet",
                                "columns": [
                                    {
                                        "type": "Column",
                                        "width": "stretch",
                                        "items": [{
                                            "type": "TextBlock",
                                            "text": f"{'✅ Auto-fix PR created' if pr_url else '⚠️ Manual fix required'}",
                                            "size": "Small",
                                            "weight": "Bolder",
                                            "color": "Good" if pr_url else "Warning",
                                        }]
                                    },
                                    {
                                        "type": "Column",
                                        "width": "auto",
                                        "items": [{
                                            "type": "TextBlock",
                                            "text": "🤖 AI Triage Agent",
                                            "size": "Small",
                                            "color": "Accent",
                                            "horizontalAlignment": "Right",
                                        }]
                                    }
                                ]
                            }
                        ]
                    }
                ],

                # ─── ACTIONS ───
                "actions": [
                    # Primary action - View PR (if exists)
                    *([{
                        "type": "Action.OpenUrl",
                        "title": "📝 View Auto-fix PR",
                        "url": pr_url,
                        "style": "positive",
                    }] if pr_url else []),

                    # Secondary actions
                    {
                        "type": "Action.OpenUrl",
                        "title": "🔗 View Full Analysis",
                        "url": actions_url,
                    } if actions_url else None,

                    # Additional context
                    {
                        "type": "Action.ShowCard",
                        "title": "📊 More Details",
                        "card": {
                            "type": "AdaptiveCard",
                            "body": [
                                {
                                    "type": "TextBlock",
                                    "text": "Additional Context",
                                    "weight": "Bolder",
                                },
                                {
                                    "type": "FactSet",
                                    "facts": [
                                        {"title": "Commit", "value": commit[:8] if commit != "unknown" else "N/A"},
                                        {"title": "Job Name", "value": job},
                                        {"title": "Full RCA", "value": "Click 'View Full Analysis' to see complete details"},
                                    ]
                                }
                            ]
                        }
                    }
                ],

                # Remove None values from actions
                "actions": [a for a in [
                    {"type": "Action.OpenUrl", "title": "📝 View PR", "url": pr_url, "style": "positive"} if pr_url else None,
                    {"type": "Action.OpenUrl", "title": "🔗 Full Analysis", "url": actions_url} if actions_url else None,
                ] if a is not None]
            }
        }]
    }

    return card


def create_summary_only_card(job, category, error_class, actions_url):
    """
    Lightweight card when full RCA isn't available yet
    """
    return {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": [
                    {
                        "type": "TextBlock",
                        "text": "⏳ Pipeline Failure - Analysis in Progress",
                        "weight": "Bolder",
                        "size": "Large",
                        "color": "Warning",
                    },
                    {
                        "type": "FactSet",
                        "facts": [
                            {"title": "Job", "value": job},
                            {"title": "Category", "value": category},
                            {"title": "Error", "value": error_class},
                            {"title": "Status", "value": "AI agent analyzing..."},
                        ]
                    }
                ],
                "actions": [{
                    "type": "Action.OpenUrl",
                    "title": "View Progress",
                    "url": actions_url,
                }] if actions_url else []
            }
        }]
    }


# ─── EXAMPLE USAGE ───

if __name__ == "__main__":
    # Test data
    sample_rca = """
    Root Cause:
    The Playwright test failed because the selector 'button.submit' could not be found on the page.
    This is likely due to a recent UI change where the button class was renamed from 'submit' to 'submit-btn'.
    The test is timing out after 30 seconds while waiting for this element.

    Recommended Fix:
    1. Update the selector in tests/login.spec.js from 'button.submit' to 'button.submit-btn'
    2. Alternatively, use a more stable data-testid attribute: [data-testid="submit-button"]
    3. Increase the timeout to 60s in playwright.config.js as a safety margin

    Confidence: High
    This is a straightforward selector mismatch that can be easily verified by inspecting the page.
    """

    card = create_enhanced_teams_card(
        job="CI-Pipeline",
        branch="feature/user-auth",
        category="playwright-e2e",
        error_class="TimeoutError",
        rca=sample_rca,
        pr_url="https://github.com/org/repo/pull/123",
        actions_url="https://github.com/org/repo/actions/runs/456",
        commit="abc1234"
    )

    import json
    print(json.dumps(card, indent=2))
