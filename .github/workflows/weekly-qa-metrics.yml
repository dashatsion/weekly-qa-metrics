name: Weekly QA Control Chart Metrics

on:
  schedule:
    # Кожен понеділок о 6:00 AM Arizona Time (13:00 UTC)
    # Arizona не змінює час, тому завжди UTC-7
    - cron: '0 13 * * 1'
  workflow_dispatch: # Дозволяє запуск вручну для тестування

jobs:
  send-qa-metrics:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v4
      
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
        
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        
    - name: Debug environment variables
      env:
        JIRA_EMAIL: ${{ secrets.JIRA_EMAIL }}
        JIRA_BASE_URL: ${{ secrets.JIRA_BASE_URL }}
      run: |
        echo "JIRA_EMAIL is set: $([ -n "$JIRA_EMAIL" ] && echo "YES" || echo "NO")"
        echo "JIRA_BASE_URL is set: $([ -n "$JIRA_BASE_URL" ] && echo "YES" || echo "NO")"
        echo "JIRA_API_TOKEN is set: $([ -n "${{ secrets.JIRA_API_TOKEN }}" ] && echo "YES" || echo "NO")"
        echo "SLACK_WEBHOOK_URL is set: $([ -n "${{ secrets.SLACK_WEBHOOK_URL }}" ] && echo "YES" || echo "NO")"
        echo "JIRA_BASE_URL format: ${JIRA_BASE_URL:0:20}..."
        
    - name: Test Jira connection
      env:
        SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
        JIRA_EMAIL: ${{ secrets.JIRA_EMAIL }}
        JIRA_API_TOKEN: ${{ secrets.JIRA_API_TOKEN }}
        JIRA_BASE_URL: ${{ secrets.JIRA_BASE_URL }}
      run: python scripts/test_jira.py
        
    - name: Generate and send QA metrics
      env:
        SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
        JIRA_EMAIL: ${{ secrets.JIRA_EMAIL }}
        JIRA_API_TOKEN: ${{ secrets.JIRA_API_TOKEN }}
        JIRA_BASE_URL: ${{ secrets.JIRA_BASE_URL }}
      run: python scripts/qa_metrics.py
