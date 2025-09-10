#!/usr/bin/env python3
import os
import requests
from datetime import datetime, timedelta
import pytz

def debug_jira_statuses():
    """Перевіряє які статуси існують в Jira та знаходить issues"""
    
    jira_email = os.environ['JIRA_EMAIL']
    jira_token = os.environ['JIRA_API_TOKEN']
    jira_url = os.environ['JIRA_BASE_URL'].rstrip('/')
    
    session = requests.Session()
    session.auth = (jira_email, jira_token)
    session.headers.update({'Accept': 'application/json'})
    
    projects = ['GS2', 'GS1', 'PS2', 'GS5', 'RD1', 'GS3']
    
    print("=== DEBUG: Перевірка статусів та issues ===\n")
    
    # Отримуємо дати
    kyiv_tz = pytz.timezone('Europe/Kiev')
    now = datetime.now(kyiv_tz)
    
    # Поточний тиждень
    days_since_monday = now.weekday()
    monday_this_week = now - timedelta(days=days_since_monday)
    start_date = monday_this_week.replace(hour=0, minute=1)
    end_date = now.replace(hour=23, minute=59)
    
    print(f"Шукаємо за період: {start_date} - {end_date}\n")
    
    for project in projects:
        print(f"=== ПРОЕКТ {project} ===")
        
        # 1. Шукаємо всі issues в проекті за період
        jql_all = f'project = {project} AND created >= "{start_date.strftime("%Y-%m-%d")}"'
        print(f"JQL всі issues: {jql_all}")
        
        try:
            url = f"{jira_url}/rest/api/2/search"
            response = session.get(url, params={
                'jql': jql_all,
                'maxResults': 50,
                'fields': 'key,status,created'
            })
            
            if response.status_code == 200:
                data = response.json()
                issues = data['issues']
                print(f"Знайдено {len(issues)} issues в {project}")
                
                # Показуємо статуси
                statuses = set()
                for issue in issues:
                    status = issue['fields']['status']['name']
                    statuses.add(status)
                    print(f"  {issue['key']}: {status}")
                
                print(f"Унікальні статуси в {project}: {list(statuses)}")
                
                # 2. Шукаємо з різними варіантами Ready For QA
                qa_variants = [
                    "Ready For QA",
                    "Ready for QA", 
                    "Ready for qa",
                    "READY FOR QA",
                    "Ready For Testing",
                    "Ready for Testing"
                ]
                
                for variant in qa_variants:
                    jql_qa = f'project = {project} AND status = "{variant}"'
                    response_qa = session.get(url, params={
                        'jql': jql_qa,
                        'maxResults': 10,
                        'fields': 'key,status'
                    })
                    
                    if response_qa.status_code == 200:
                        qa_data = response_qa.json()
                        if qa_data['total'] > 0:
                            print(f"  ✅ Знайдено {qa_data['total']} issues зі статусом '{variant}'")
                            for issue in qa_data['issues']:
                                print(f"    - {issue['key']}")
                        else:
                            print(f"  ❌ Не знайдено issues зі статусом '{variant}'")
            else:
                print(f"Помилка запиту для {project}: {response.status_code}")
                
        except Exception as e:
            print(f"Помилка для {project}: {e}")
        
        print()

if __name__ == "__main__":
    debug_jira_statuses()
