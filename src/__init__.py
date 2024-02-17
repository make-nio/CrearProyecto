# src/__init__.py
import os
from dotenv import load_dotenv
import requests
from git import Repo
import base64
import nacl.encoding
import nacl.utils
from nacl.public import PrivateKey, SealedBox
import json
from git import Repo, GitCommandError

load_dotenv()  # Esto carga las variables de entorno del archivo .env

GITHUB_USERNAME = os.getenv('GITHUB_USERNAME')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_API_URL = 'https://api.github.com'

headers = {
    'Authorization': f'Bearer {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json',
    'X-GitHub-Api-Version': '2022-11-28'
}

def authenticate_to_github():

    response = requests.get(f'{GITHUB_API_URL}/octocat', headers=headers)
    if response.status_code == 200:
        print('Autenticación exitosa.')
        return True
    else:
        print('Error en la autenticación.', response.status_code)
        return False
    
def create_github_repository(repo_name, repo_description):
    """
    Crea un nuevo repositorio en GitHub con el nombre y descripción proporcionados.
    """
    data = {
        'name': repo_name,
        'description': repo_description,
        'auto_init': True  # Esto crea el repositorio con un README inicial
    }
    response = requests.post(f'{GITHUB_API_URL}/user/repos', headers=headers, json=data)
    if response.status_code == 201:
        print('Repositorio creado exitosamente.')
        return response.json()
    else:
        print('Error al crear el repositorio.')
        return None

def set_github_secrets(repo_name, docker_user, docker_password):
    """
    Configura secrets en el repositorio de GitHub, como las credenciales de Docker.
    """
    # Obtener la clave pública de GitHub para tu repositorio
    public_key_response = requests.get(f"{GITHUB_API_URL}/repos/{GITHUB_USERNAME}/{repo_name}/actions/secrets/public-key", headers=headers)
    
    if public_key_response.status_code != 200:
        print(f"Error al obtener la clave pública: {public_key_response.status_code}")
        return
    
    public_key = public_key_response.json()['key']
    public_key_id = public_key_response.json()['key_id']
    
    # Encrypt your secrets using the public key
    def encrypt_secret(public_key: str, secret_value: str) -> str:
        public_key_bytes = base64.b64decode(public_key)
        sealed_box = SealedBox(nacl.public.PublicKey(public_key_bytes))
        encrypted = sealed_box.encrypt(secret_value.encode())
        return base64.b64encode(encrypted).decode()
    
    # Encrypted secrets
    encrypted_docker_user = encrypt_secret(public_key, docker_user)
    encrypted_docker_password = encrypt_secret(public_key, docker_password)
    
    # Ahora, establece los secrets en el repositorio usando la API de GitHub
    secrets = {
        'DOCKER_USER': encrypted_docker_user,
        'DOCKER_PASSWORD': encrypted_docker_password
    }
    
    for name, encrypted_value in secrets.items():
        secret_url = f"{GITHUB_API_URL}/repos/{GITHUB_USERNAME}/{repo_name}/actions/secrets/{name}"
        encrypted_secret_data = {
            'encrypted_value': encrypted_value,
            'key_id': public_key_id
        }
        response = requests.put(secret_url, headers=headers, json=encrypted_secret_data)
        if response.status_code == 201 or response.status_code == 204:
            print(f"Secret {name} configurado correctamente.")
        else:
            print(f"Error al configurar el secret {name}: {response.status_code}")

def get_default_branch_sha(repo_name):
    """
    Obtiene el SHA del último commit de la rama por defecto.
    """
    default_branch_info = requests.get(f"{GITHUB_API_URL}/repos/{GITHUB_USERNAME}/{repo_name}", headers=headers)
    if default_branch_info.status_code == 200:
        default_branch = default_branch_info.json()['default_branch']
        default_branch_sha_info = requests.get(f"{GITHUB_API_URL}/repos/{GITHUB_USERNAME}/{repo_name}/git/refs/heads/{default_branch}", headers=headers)
        if default_branch_sha_info.status_code == 200:
            return default_branch_sha_info.json()['object']['sha']
    return None

def create_branch(repo_name, branch_name, sha):
    """
    Crea una rama en el repositorio de GitHub con el SHA proporcionado.
    """
    data = {'ref': f"refs/heads/{branch_name}", 'sha': sha}
    response = requests.post(f"{GITHUB_API_URL}/repos/{GITHUB_USERNAME}/{repo_name}/git/refs", headers=headers, json=data)
    if response.status_code == 201:
        print(f'Rama {branch_name} creada correctamente.')
        return True
    else:
        print(f'Error al crear la rama {branch_name}: {response.status_code}')
        return False

def get_first_commit_sha(repo_name):
    """
    Obtiene el SHA del primer commit del repositorio especificado.
    """
    commits_response = requests.get(f"{GITHUB_API_URL}/repos/{GITHUB_USERNAME}/{repo_name}/commits", headers=headers)
    if commits_response.status_code == 200:
        commits = commits_response.json()
        if commits:
            first_commit_sha = commits[-1]['sha']
            print(f"Primer commit SHA: {first_commit_sha}")
            return first_commit_sha
    print(f"No se pudo obtener la información de commits: {commits_response.status_code}")
    return None

def create_branches(repo_name):
    """
    Crea las ramas 'master' y 'feature/initial' en el repositorio de GitHub.
    """
    # Crea la rama 'master' basada en el primer commit del repositorio
    first_commit_sha = get_first_commit_sha(repo_name)
    if not first_commit_sha:
        print("No se pudo obtener el SHA del primer commit.")
        return False

    # Crea la rama 'feature/initial' a partir de la rama 'master' recién creada
    if not create_branch(repo_name, 'feature/initial', first_commit_sha):
        return False

    print("Rama creadas con éxito.")
    return True

def clone_template_repository(template_url, local_path):
    """
    Clona el repositorio de la plantilla en el directorio local especificado.
    """
    Repo.clone_from(template_url, local_path)
    print(f'Repositorio clonado en {local_path}.')

def modify_and_push_changes(local_path, repo_name, repo_description, remote_url):
    print(f"Comenzando el proceso en el directorio: {local_path}")
    
    # Intenta cambiar al directorio local del repositorio
    try:
        os.chdir(local_path)
        print(f"Cambio de directorio exitoso.")
        repo = Repo('.')
        print(f"Repositorio en '{local_path}' cargado correctamente.")
    except Exception as e:
        print(f"Error al cambiar al directorio {local_path} o cargar el repositorio: {e}")
        return False


    # Modificar package.json
    package_json_path = os.path.join(local_path, 'package.json')
    with open(package_json_path, 'r+') as file:
        package_data = json.load(file)
        package_data['name'] = repo_name
        package_data['description'] = repo_description
        file.seek(0)  # Vuelve al comienzo del archivo
        json.dump(package_data, file, indent=2)
        file.truncate()  # Eliminar el resto del archivo en caso de que sea más corto ahora
    
    # Modificar README.md
    readme_path = os.path.join(local_path, 'README.md')
    with open(readme_path, 'w') as file:  # Abre el archivo en modo escritura para sobrescribir
        # Crear el nuevo contenido del README
        new_readme_content = f"# {repo_name}\n\n{repo_description}\n"
        file.write(new_readme_content)


    # Establecer el remoto a la URL correcta
    print(f"Estableciendo URL del remoto para 'origin'.")
    try:
        origin = repo.remotes.origin
        origin.set_url(remote_url)
        print(f"URL del remoto 'origin' actualizada a {remote_url}.")
    except AttributeError:
        origin = repo.create_remote('origin', remote_url)
        print(f"Remoto 'origin' creado con la URL {remote_url}.") 

    # Sincronizar con el remoto antes de hacer el push
    print("Sincronizando con el repositorio remoto...")
    repo.git.fetch()

    # Asegurarse de que la rama 'feature/initial' exista y cambiar a ella
    if 'feature/initial' not in repo.heads:
        repo.git.checkout('-b', 'feature/initial')
    else:
        repo.git.checkout('feature/initial')    

    # Verificar si el remoto ya está configurado, si no, agregarlo
    try:
        origin = repo.remote('origin')
    except ValueError:
        # El remoto no existe, así que lo agregamos
        origin = repo.create_remote('origin', remote_url)

    # Verificar cambios y hacer commit
    if repo.is_dirty(untracked_files=True):
        repo.git.add(A=True)
        repo.index.commit('Initial commit with modified template files.')
        print("Cambios añadidos al commit.")
    else:
        print("No hay cambios para hacer commit.")
        return True

    # Forzar push a la rama 'feature/initial'
    print("Realizando push forzado a la rama 'feature/initial' del repositorio remoto.")
    try:
        origin.push(refspec='feature/initial:feature/initial', force=True)
        print('Cambios forzados subidos a la rama feature/initial del repositorio remoto.')
        return True
    except GitCommandError as e:
        print(f"Error al realizar push forzado al repositorio remoto: {e}")
        return False
    
def merge_with_unrelated_histories(local_path):
    try:
        # Cambia al directorio del repositorio local
        os.chdir(local_path)
        
        # Carga el repositorio
        repo = Repo('.')
        
        # Asegúrate de que todas las ramas remotas estén actualizadas localmente
        repo.git.fetch('--all')

        # Verifica si la rama 'main' existe localmente, si no, haz checkout a ella desde el remoto
        if 'main' not in repo.branches:
            repo.git.checkout('-t', 'origin/main')
        else:
            repo.git.checkout('main')
        
        # Realiza el merge forzado
        repo.git.merge('origin/feature/initial', '--allow-unrelated-histories', '--strategy-option', 'theirs')

        # Si hay conflictos, se resuelven automáticamente tomando la versión de 'feature/initial'
        
        # Realiza el commit si es necesario
        if repo.is_dirty(untracked_files=True):
            repo.git.commit('-am', 'Merge with unrelated histories resolved')
        
        # Empuja los cambios al remoto
        try:
            repo.git.push('origin', 'main', force=True)
            print(f"Push forzado de 'feature/initial' a 'main' realizado con éxito.")
        except GitCommandError as e:
            print(f"Error durante el push forzado: {e}")
            return False
    except GitCommandError as e:
        print(f"Error durante el merge: {e}")
        return False