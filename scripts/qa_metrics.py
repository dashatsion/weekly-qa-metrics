#!/usr/bin/env python3
import os
import requests
from datetime import datetime, timedelta
import pytz
from statistics import median

class QAMetricsCollector:
    def __init__(self):
        self.jira_email = os.environ['JIRA_EMAIL']
        self.jira_token = os.environ['JIRA_API_TOKEN']
        self.jira_url = os.environ['JIRA_BASE_URL'].rstrip('/')
        self.slack_webhook = os.environ['SLACK_WEBHOOK_URL']
        
        self.session = requests.Session()
        self.session.auth = (self.jira_email, self.jira_token)
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
        self.projects = ['GS2', 'GS1', 'PS2', 'GS5', 'RD1', 'GS3']
    
    def search_issues(self, jql, max_results=1000):
        """Пошук issues через REST API"""
        url = f"{self.jira_url}/rest/api/2/search"
        
        params = {
            'jql': jql,
            'maxResults': max_results,
            'expand': 'changelog',
            'fields': 'created,status'
        }
        
        print(f"Запит до: {url}")
        print(f"JQL: {jql}")
        
        response = self.session.get(url, params=params, timeout=60)
        print(f"Статус відповіді: {response.status_code}")
        
        response.raise_for_status()
        data = response.json()
        
        print(f"Знайдено issues: {len(data['issues'])}")
        return data['issues']
    
    def get_date_range(self):
        """Отримує діапазон дат за поточний тиждень для тестування"""
        kyiv_tz = pytz.timezone('Europe/Kiev')
        now = datetime.now(kyiv_tz)
        
        # Беремо останні 7 днів для тестування
        start_date = now - timedelta(days=7)
        end_date = now
        
        return start_date, end_date
    
    def get_ready_for_qa_metrics(self, project, start_date, end_date):
        """Отримує метрики Ready For QA для проекту за період"""
        
        print(f"\n=== Обробляю проект {project} ===")
        
        # Спочатку подивимося які issues взагалі є
        jql_all = f'project = {project} AND created >= "{start_date.strftime("%Y-%m-%d")}"'
        
        try:
            all_issues = self.search_issues(jql_all, max_results=50)
            
            print(f"Всього issues в {project} за період: {len(all_issues)}")
            
            # Показуємо статуси
            if all_issues:
                print("Статуси знайдених issues:")
                for issue in all_issues[:10]:  # показуємо перші 10
                    status = issue['fields']['status']['name']
                    print(f"  {issue['key']}: {status}")
            
            # Тепер шукаємо з точним статусом з вашої Jira
            jql_qa = f'project = {project} AND status = "Ready For QA"'
            qa_issues = self.search_issues(jql_qa, max_results=50)
            
            if qa_issues:
                print(f"Issues зі статусом 'Ready For QA': {len(qa_issues)}")
                for issue in qa_issues:
                    print(f"  - {issue['key']}")
            else:
                print("Не знайдено issues зі статусом 'Ready For QA'")
                
                # Спробуємо варіанти
                variants = ["Ready for QA", "READY FOR QA", "Ready for Testing"]
                for variant in variants:
                    jql_variant = f'project = {project} AND status = "{variant}"'
                    try:
                        variant_issues = self.search_issues(jql_variant, max_results=10)
                        if variant_issues:
                            print(f"Знайдено {len(variant_issues)} issues зі статусом '{variant}'")
                            break
                    except:
                        continue
            
            return "0h 0m"  # Поки що повертаємо 0, поки не знайдемо правильний статус
                
        except Exception as e:
            print(f"Помилка при отриманні метрик для {project}: {e}")
            return "N/A"
    
    def format_time(self, hours):
        """Форматує час у годинах в формат 'Xh Ym'"""
        total_hours = int(hours)
        minutes = int((hours - total_hours) * 60)
        return f"{total_hours}h {minutes}m"
    
    def collect_all_metrics(self):
        """Збирає метрики для всіх проектів"""
        start_date, end_date = self.get_date_range()
        
        print(f"Збираю метрики за період: {start_date.strftime('%Y-%m-%d %H:%M')} - {end_date.strftime('%Y-%m-%d %H:%M')}")
        
        metrics = {}
        for project in self.projects:
            metrics[project] = self.get_ready_for_qa_metrics(project, start_date, end_date)
        
        return metrics, start_date, end_date
    
    def format_slack_message(self, metrics, start_date, end_date):
        """Форматує повідомлення для Slack"""
        message = f"*Control Chart, median time {start_date.strftime('%b %d')}- {end_date.strftime('%b %d')} за київським часом (тест)*\n\n"
        
        for project in self.projects:
            message += f"{project} - {metrics[project]}\n"
        
        return message.strip()
    
    def send_to_slack(self, message):
        """Відправляє повідомлення в Slack"""
        payload = {
            "channel": "#control-chart",
            "text": message,
            "username": "QA Metrics Bot",
            "icon_emoji": ":chart_with_upwards_trend:"
        }
        
        try:
            response = requests.post(self.slack_webhook, json=payload, timeout=30)
            if response.status_code == 200:
                print("✅ Метрики успішно відправлені в Slack!")
            else:
                print(f"❌ Помилка відправки в Slack: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Помилка при відправці: {e}")
    
    def run(self):
        """Основний метод для запуску збору та відправки метрик"""
        print("🚀 Запуск збору QA метрик...")
        
        try:
            metrics, start_date, end_date = self.collect_all_metrics()
            message = self.format_slack_message(metrics, start_date, end_date)
            
            print("\n📊 Зібрані метрики:")
            print(message)
            print("\n📤 Відправляю в Slack...")
            
            self.send_to_slack(message)
            
        except Exception as e:
            error_message = f"❌ Помилка при збиранні метрик: {e}"
            print(error_message)

if __name__ == "__main__":
    collector = QAMetricsCollector()
    collector.run()
