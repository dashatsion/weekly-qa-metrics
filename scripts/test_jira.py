#!/usr/bin/env python3
import os
import requests

def test_jira_connection():
    """Тестує підключення до Jira"""
    
    # Отримуємо креденшали
    jira_email = os.environ.get('JIRA_EMAIL')
    jira_token = os.environ.get('JIRA_API_TOKEN')
    jira_url = os.environ.get('JIRA_BASE_URL')
    
    print(f"🔗 Тестуємо підключення до: {jira_url}")
    print(f"📧 Email: {jira_email}")
    print(f"🔑 Token: {'✅ Встановлено (' + str(len(jira_token)) + ' символів)' if jira_token else '❌ Не встановлено'}")
    
    if not all([jira_email, jira_token, jira_url]):
        print("❌ Не всі креденшали встановлені!")
        return False
    
    # Очищаємо URL від зайвих слешів
    jira_url = jira_url.rstrip('/')
    
    try:
        # Тестуємо простий запит до server info
        print(f"\n🌐 Тестуємо HTTP доступ до: {jira_url}/rest/api/2/serverInfo")
        
        response = requests.get(
            f"{jira_url}/rest/api/2/serverInfo", 
            auth=(jira_email, jira_token), 
            timeout=30,
            headers={'Accept': 'application/json'}
        )
        
        print(f"📡 Статус відповіді: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ HTTP підключення успішне!")
            try:
                server_info = response.json()
                print(f"📊 Jira версія: {server_info.get('version', 'N/A')}")
                print(f"🏢 Server Title: {server_info.get('serverTitle', 'N/A')}")
            except:
                print("⚠️  Отримано відповідь, але не в JSON форматі")
        elif response.status_code == 401:
            print("❌ Помилка авторизації (401) - перевірте email та API token")
            return False
        elif response.status_code == 403:
            print("❌ Доступ заборонено (403) - недостатньо прав")
            return False
        elif response.status_code == 404:
            print("❌ Не знайдено (404) - перевірте URL Jira")
            return False
        else:
            print(f"❌ HTTP помилка: {response.status_code}")
            print(f"Response: {response.text[:200]}...")
            return False
        
        # Тестуємо запит проектів
        print(f"\n📁 Тестуємо отримання проектів...")
        projects_response = requests.get(
            f"{jira_url}/rest/api/2/project", 
            auth=(jira_email, jira_token), 
            timeout=30,
            headers={'Accept': 'application/json'}
        )
        
        print(f"📡 Статус відповіді проектів: {projects_response.status_code}")
        
        if projects_response.status_code == 200:
            projects = projects_response.json()
            print(f"✅ Знайдено {len(projects)} проектів!")
            
            # Показуємо перші кілька проектів
            for project in projects[:5]:
                print(f"  - {project['key']}: {project['name']}")
            
            # Перевіряємо наші проекти
            our_projects = ['GS2', 'GS1', 'PS2', 'GS5', 'RD1', 'GS3']
            existing_keys = [p['key'] for p in projects]
            
            print(f"\n🎯 Перевіряємо наші цільові проекти:")
            for project in our_projects:
                if project in existing_keys:
                    print(f"  ✅ {project} - знайдено")
                else:
                    print(f"  ❌ {project} - НЕ знайдено")
        else:
            print(f"❌ Не вдалося отримати проекти: {projects_response.status_code}")
        
        return True
        
    except requests.exceptions.ConnectTimeout:
        print("❌ Таймаут підключення - сервер не відповідає")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Помилка з'єднання: {e}")
        return False
    except Exception as e:
        print(f"❌ Загальна помилка: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Запуск детального тесту Jira підключення...\n")
    success = test_jira_connection()
    
    if success:
        print("\n🎉 Тест пройшов успішно!")
    else:
        print("\n💥 Тест провалився. Перевірте налаштування.")
        print("\n🔧 Можливі причини:")
        print("1. Неправильний JIRA_BASE_URL (має бути https://yourcompany.atlassian.net)")
        print("2. Неправильний JIRA_EMAIL")
        print("3. Неправильний або застарілий JIRA_API_TOKEN")
        print("4. Обмеження доступу в мережі")
        
        print("\n💡 Як отримати правильні дані:")
        print("- JIRA_BASE_URL: URL з браузера, наприклад https://yourcompany.atlassian.net")
        print("- JIRA_EMAIL: ваш email в Jira")
        print("- JIRA_API_TOKEN: створіть в Jira → Profile → Personal Access Tokens")
