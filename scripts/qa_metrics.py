#!/usr/bin/env python3
import os
import requests
from datetime import datetime, timedelta
import pytz
from statistics import median

class JiraMetricsCollector:
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
    
    def get_issues_transitioned_to_qa(self, project):
        """Знаходить issues що перейшли в Ready for QA за Sep 1-5"""
        
        # JQL для пошуку issues що перейшли в Ready for QA за період
        jql = f'project = {project} AND status changed to "Ready for QA" DURING ("2025-09-01", "2025-09-05")'
        
        url = f"{self.jira_url}/rest/api/2/search"
        params = {
            'jql': jql,
            'expand': 'changelog',
            'fields': 'created,key',
            'maxResults': 100
        }
        
        try:
            response = self.session.get(url, params=params, timeout=60)
            response.raise_for_status()
            return response.json()['issues']
        except Exception as e:
            print(f"Помилка для {project}: {e}")
            return []
    
    def calculate_working_hours(self, start_time, end_time):
        """Рахує робочі години між двома датами (понеділок-п'ятниця)"""
        kyiv_tz = pytz.timezone('Europe/Kiev')
        
        # Конвертуємо в київський час
        if start_time.tzinfo is None:
            start_time = kyiv_tz.localize(start_time)
        else:
            start_time = start_time.astimezone(kyiv_tz)
            
        if end_time.tzinfo is None:
            end_time = kyiv_tz.localize(end_time)
        else:
            end_time = end_time.astimezone(kyiv_tz)
        
        total_hours = 0
        current_date = start_time.date()
        end_date = end_time.date()
        
        while current_date <= end_date:
            # Перевіряємо чи це робочий день (0=понеділок, 6=неділя)
            if current_date.weekday() < 5:  # понеділок-п'ятниця
                if current_date == start_time.date() and current_date == end_date:
                    # Той самий день
                    total_hours += (end_time - start_time).total_seconds() / 3600
                elif current_date == start_time.date():
                    # Перший день - від start_time до кінця дня
                    end_of_day = datetime.combine(current_date, datetime.min.time()).replace(hour=23, minute=59, tzinfo=kyiv_tz)
                    total_hours += (end_of_day - start_time).total_seconds() / 3600
                elif current_date == end_date:
                    # Останній день - від початку дня до end_time
                    start_of_day = datetime.combine(current_date, datetime.min.time()).replace(hour=0, minute=1, tzinfo=kyiv_tz)
                    total_hours += (end_time - start_of_day).total_seconds() / 3600
                else:
                    # Повний робочий день (24 години)
                    total_hours += 24
            
            current_date += timedelta(days=1)
        
        return total_hours
    
    def calculate_time_to_qa(self, issue):
        """Рахує час від створення до Ready for QA для конкретного issue"""
        try:
            # Час створення
            created_str = issue['fields']['created']
            created_time = datetime.strptime(created_str[:19], '%Y-%m-%dT%H:%M:%S')
            
            # Шукаємо перехід в Ready for QA в changelog
            qa_transition_time = None
            
            if 'changelog' in issue:
                for history in issue['changelog']['histories']:
                    for item in history['items']:
                        if (item['field'] == 'status' and 
                            item['toString'] == 'Ready for QA'):
                            
                            transition_str = history['created']
                            qa_transition_time = datetime.strptime(
                                transition_str[:19], '%Y-%m-%dT%H:%M:%S'
                            )
                            break
                    if qa_transition_time:
                        break
            
            if qa_transition_time:
                # Рахуємо робочі години замість календарних
                working_hours = self.calculate_working_hours(created_time, qa_transition_time)
                return max(0, working_hours)  # не може бути негативним
            
            return None
            
        except Exception as e:
            print(f"Помилка обчислення для {issue['key']}: {e}")
            return None
    
    def format_time(self, hours):
        """Форматує час у годинах в формат 'Xh Ym'"""
        if hours is None:
            return "N/A"
        
        total_hours = int(hours)
        minutes = int((hours - total_hours) * 60)
        return f"{total_hours}h {minutes}m"
    
    def collect_metrics_for_project(self, project):
        """Збирає метрики для одного проекту"""
        print(f"\nОбробляю проект {project}...")
        
        issues = self.get_issues_transitioned_to_qa(project)
        print(f"Знайдено {len(issues)} issues що перейшли в Ready for QA")
        
        if not issues:
            return "0h 0m"
        
        times = []
        for issue in issues:
            issue_key = issue['key']
            time_hours = self.calculate_time_to_qa(issue)
            
            if time_hours is not None:
                times.append(time_hours)
                print(f"  {issue_key}: {self.format_time(time_hours)}")
            else:
                print(f"  {issue_key}: не вдалося обчислити")
        
        if times:
            median_hours = median(times)
            result = self.format_time(median_hours)
            print(f"Median для {project}: {result}")
            return result
        else:
            print(f"Немає валідних даних для {project}")
            return "0h 0m"
    
    def collect_all_metrics(self):
        """Збирає метрики для всіх проектів"""
        print("Збираю метрики за період Sep 1-5, 2025...")
        
        metrics = {}
        for project in self.projects:
            metrics[project] = self.collect_metrics_for_project(project)
        
        return metrics
    
    def format_slack_message(self, metrics):
        """Форматує повідомлення для Slack"""
        message = "*Control Chart, median time Sep 1- Sep 5 з 00:01 до 23:59 за київським часом (робочі дні)*\n\n"
        
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
                print("Метрики успішно відправлені в Slack!")
            else:
                print(f"Помилка відправки в Slack: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Помилка при відправці: {e}")
    
    def run(self):
        """Основний метод для запуску збору та відправки метрик"""
        print("Запуск збору QA метрик через Jira REST API...")
        
        try:
            metrics = self.collect_all_metrics()
            message = self.format_slack_message(metrics)
            
            print(f"\nЗібрані метрики:")
            print(message)
            print("\nВідправляю в Slack...")
            
            self.send_to_slack(message)
            
        except Exception as e:
            error_message = f"Помилка при збиранні метрик: {e}"
            print(error_message)
            
            # Відправляємо повідомлення про помилку в Slack
            self.send_to_slack(f"Помилка при генерації Control Chart метрик:\n```{error_message}```")

if __name__ == "__main__":
    collector = JiraMetricsCollector()
    collector.run()
