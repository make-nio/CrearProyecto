# main.py
from dotenv import load_dotenv
import os
from src import (authenticate_to_github, create_github_repository, set_github_secrets, create_branches, clone_template_repository, modify_and_push_changes,merge_with_unrelated_histories)


load_dotenv()  # Esto carga las variables de entorno del archivo .env

def main():
    # Configuración de variables a través de variables de entorno
    github_username = os.getenv('GITHUB_USERNAME')
    repo_name = os.getenv('REPO_NAME')
    repo_description = os.getenv('REPO_DESCRIPTION')
    docker_user = os.getenv('DOCKER_USER')
    docker_password = os.getenv('DOCKER_PASSWORD')
    template_url = os.getenv('TEMPLATE_URL')
    local_path = os.getenv('LOCAL_PATH')

    remote_url = f'https://github.com/{github_username}/{repo_name}.git'

    
     # Ejecución de funciones
    authenticate_to_github()
    create_github_repository(repo_name, repo_description)
    set_github_secrets(repo_name, docker_user, docker_password)
    create_branches(repo_name)
    clone_template_repository(template_url, local_path)
    modify_and_push_changes(local_path, repo_name, repo_description, remote_url)
    merge_with_unrelated_histories(local_path)

if __name__ == "__main__":
    main()
