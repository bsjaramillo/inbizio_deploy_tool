import paramiko
import argparse
import subprocess
import os
from dotenv import load_dotenv

load_dotenv()

SERVER_HOST = os.getenv('SERVER_HOST')
SERVER_PORT = int(os.getenv('SERVER_PORT'))
SERVER_USER = os.getenv('SERVER_USER')
SERVER_PASSWORD = os.getenv('SERVER_PASSWORD')
SSH_KEY_PATH = os.path.expanduser(os.getenv('SSH_KEY_PATH'))
INBIZIO_PROJECT_PATH = os.path.expanduser(os.getenv('INBIZIO_PROJECT_PATH'))
INBIZIO_REMOTE_PATH = os.getenv('INBIZIO_REMOTE_PATH')
INBIZIO_REMOTE_DEPLOY_PATH = os.getenv('INBIZIO_REMOTE_DEPLOY_PATH')


def execute_command(ssh, command, local=False):
    if local:
        result = subprocess.run(command, shell=True, check=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output, error = result.stdout, result.stderr
        print(f'Executing: {command}')
        print(output)
        if error:
            print(error)
        return output, error
    else:
        stdin, stdout, stderr = ssh.exec_command(command)
        output = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')
        print(f'Executing: {command}')
        print(output)
        if error:
            print(error)
        return output, error


class InbizioDeployTool:
    def __init__(self):
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def connect(self):
        try:
            self.ssh_client.connect(SERVER_HOST, SERVER_PORT,
                                    SERVER_USER, SERVER_PASSWORD)
            print('Connected to the server with password')
        except paramiko.ssh_exception.AuthenticationException:
            self.ssh_client.connect(SERVER_HOST, SERVER_PORT,
                                    SERVER_USER, key_filename=SSH_KEY_PATH)
            print('Connected to the server with SSH key')
        except paramiko.ssh_exception.SSHException as e:
            print(f'Error: {e}')

    def zip_deploy(self, version):
        output, error = execute_command(
            self.ssh_client, f'cd {INBIZIO_PROJECT_PATH}/dist && zip -r inbizio{version}.zip .', local=True)
        if error:
            raise Exception('Error compressing the build folder: '+error)

    def remove_old_deploy(self):
        try:
            self.ssh_client.exec_command(
                f'rm -r {INBIZIO_REMOTE_PATH}/*')
        except Exception as e:
            raise Exception(f'Error removing old deploy: {e}')
        try:
            self.ssh_client.exec_command(
                f'rm -r {INBIZIO_REMOTE_DEPLOY_PATH}/*')
        except Exception as e:
            raise Exception(f'Error removing old deploy: {e}')
        print('Removed old deploy')

    def upload_deploy(self, version):
        deploy_path = os.path.join(
            INBIZIO_PROJECT_PATH, 'dist', f'inbizio{version}.zip')
        if not os.path.exists(deploy_path):
            raise Exception(
                f'The deploy file in path {deploy_path} does not exist')
        try:
            sftp = self.ssh_client.open_sftp()
            print('Uploading the deploy...')
            sftp.put(deploy_path,
                     f'{INBIZIO_REMOTE_PATH}/inbizio{version}.zip')
            print('Deploy uploaded')
        except Exception as e:
            raise Exception(f'Error uploading the build folder: {e}')
        finally:
            sftp.close()

    def unzip_deploy(self, version):
        try:
            execute_command(
                self.ssh_client, f'unzip {INBIZIO_REMOTE_PATH}/inbizio{version}.zip -d {INBIZIO_REMOTE_DEPLOY_PATH}/html')
        except Exception as e:
            raise Exception(f'Error unzipping the build folder: {e}')

    def deploy(self, version):
        self.connect()
        self.zip_deploy(version)
        self.remove_old_deploy()
        self.upload_deploy(version)
        self.unzip_deploy(version)

    def close(self):
        self.ssh_client.close()


if __name__ == '__main__':
    args_parser = argparse.ArgumentParser(description='Inbizio Deploy Tool')
    args_parser.add_argument(
        '--version', type=str, help='Version to deploy', required=True, action='store')
    args = args_parser.parse_args()
    deploy_tool = InbizioDeployTool()
    deploy_tool.deploy(args.version)
    deploy_tool.close()
