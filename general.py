# --------------------------------------------------------------------------------------------------
# Imports
# --------------------------------------------------------------------------------------------------
import builtins as __builtin__
import glob
import importlib.util
import inspect
import logging
import mimetypes
import os
import re
import smtplib
import ssl
import subprocess
import sys
import types
from email import encoders
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Optional, Union

import pandas as pd
import pygsheets
from google.oauth2 import service_account
from IPython.core import display as ICD
from typing_extensions import Literal

# --------------------------------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------------------------------
COLORS = {    
    'purple': '\033[95m',
    'blue': '\033[94m',
    'cyan': '\033[96m',
    'green': '\033[92m',
    'yellow': '\033[93m',
    'red': '\033[91m',

    # Style.
    'bold': '\033[1m',
    'underline': '\033[4m',
    
    # Must be at the end of print statement to revert back to normal color.
    'endc': '\033[0m'
}

# --------------------------------------------------------------------------------------------------
# Methods
# --------------------------------------------------------------------------------------------------
class GeneralUtil:

    @staticmethod
    def set_option(max_rows: Optional[int] = 10, max_cols: Optional[int] = 100, col_width: Optional[int] = 50) -> None:
        """Wrapper function for pd.set_options.

        Parameters
        ----------
        max_rows : Optional[int], optional, default 10
        max_cols : Optional[int], optional, default 100
        col_width : Optional[int], optional, default 50
        """
        pd.set_option('display.max_rows', max_rows)
        pd.set_option('display.min_rows', max_rows)
        pd.set_option('display.max_columns', max_cols)
        pd.set_option('display.max_colwidth', col_width)

    @classmethod
    def print(cls, x, df_max_rows: Optional[int] = 10, color: Optional[str] = None, header: int = 0) -> None:
        """Enhanced print that can display function docstrings and dataframes.

        Parameters
        ----------
        df_max_rows : Optional[int], optional, default 10
            Sets how many rows to show from dataframe. Then reset display.max_rows to set_option() defaults.
        header : int, default 0
            Displays the print statement in the following header format where value is width of header:
            # ---------------------------
            # Header Format
            # ---------------------------
            Note that header and color and be simutaneously set.
        """
        if isinstance(x, pd.DataFrame):
            cls.set_option(max_rows=df_max_rows)
            ICD.display(x)
            cls.set_option()
        elif isinstance(x, types.FunctionType):
            __builtin__.print(inspect.getsource(x))
        else:
            if color:
                x = f"{COLORS[f'{color}']}{x}{COLORS['endc']}"

            if header:
                if header < 0:
                    raise Exception('header cannot be negatve.')
                __builtin__.print('# ' + '-'*header)
                __builtin__.print(f'# {x}')
                __builtin__.print('# ' + '-'*header)
            else:
                __builtin__.print(x)

    @staticmethod
    def send_sms(sender: str, password: str, receiver: Union[str,dict], msg: str, carrier: Optional[str] = 'verizon') -> None:
        """Send SMS message to phone number from Gmail account.

        Parameters
        ----------
        sender : str
            Gmail account
        password : str
            Password to gmail account
        receiver : str
            phone number. e.g. '1234567890' (no spaces)
        msg : str
            Message to send.
        carrier : str, optional
            Carrier of phone number message is sent to, by default 'verizon'
        """
        carriers = {
        'att':    '@mms.att.net',
        'tmobile':' @tmomail.net',
        'verizon':  '@vtext.com',
        'sprint':   '@page.nextel.com',
        'cricket':   '@mms.cricketwireless.net'
        }

        smtp_server = 'smtp.gmail.com'
        smtp_port = 587

        # Replace the number with your own, or consider using an argument\dict for multiple people.
        if isinstance(receiver, dict):
            to_number = [
                f"{info['number']}{carriers[info['carrier']]}"
                for person, info in receiver.items()
            ]
        else:
            to_number = f"{receiver}{carriers[carrier]}"

        auth = [sender, password]

        # Establish a secure session with gmail's outgoing SMTP server using your gmail account
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(auth[0], auth[1])

        # Send text message through SMS gateway of destination number
        server.sendmail(auth[0], to_number, msg)

    @classmethod
    def send_email(cls, sender, password, subject, receivers, content):
        """
        send emails to specific receivers

        params:
        ----
        sender: str
            sender's email
        password: str
            password to sender's email
        subject: str, 
            subject line
        receivers: str, 
            str of emails, split by ','(comma), no space among emails
        content: Dict,
            {'body': str,
            'attachment': [paths of files]
            }
        """
        smtp_server = 'smtp.gmail.com'
        smtp_port = 587

        msg = MIMEMultipart('mixed')
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = receivers

        msg = cls._add_email_content(msg, content)

        with smtplib.SMTP(smtp_server, smtp_port) as smtp_obj:
            smtp_obj.ehlo()
            context = ssl.create_default_context()
            smtp_obj.starttls(context=context)
            smtp_obj.login(sender, password)
            smtp_obj.sendmail(sender, msg['To'].split(','), msg.as_string())
            smtp_obj.quit()

    @staticmethod
    def _add_email_content(msg, content):
        """
        add email content

        params:
        ----
        msg: email.mime.multipart.MIMEMultipart, 
        content: Dict
        """
        if not content.keys():
            print('no content to add')
            return

        try:
            body = content['body']
            msg_text = MIMEText(body)
            msg.attach(msg_text)
        except Exception:
            print('Email has no body content.')
        path_of_files = content['attachment']

        if not path_of_files:
            print('Email has no attachments.')
            return msg

        for data_path in path_of_files:
                
            filename = data_path.split('/')[-1]
            ctype, encoding = mimetypes.guess_type(filename)
            if ctype is None or encoding is not None:
                ctype = "application/octet-stream"
            maintype, subtype = ctype.split('/', 1)

            if maintype == 'text':
                with open(data_path) as fp:
                    attachment = MIMEText(fp.read(), _subtype=subtype)
            elif maintype == 'image':
                with open(data_path, 'rb') as fp:
                    attachment = MIMEImage(fp.read(), _subtype=subtype)
            elif maintype == 'audio':
                with open(data_path, 'rb') as fp:
                    attachment = MIMEAudio(fp.read(), _subtype=subtype)
            else:
                with open(data_path, 'rb') as fp:
                    attachment = MIMEBase(maintype, subtype)
                    attachment.set_payload(fp.read())
                encoders.encode_base64(attachment)

            attachment.add_header('Content-Disposition', 'attachment', filename=filename)
            msg.attach(attachment)
        return msg

    @staticmethod
    def get_gsheet_reader(cred: Dict) -> pygsheets.client.Client:
        """Get a google sheet reader to interact with google sheets.
        
        Parameters
        ----------
        cred : Dict
            dictionary containing the private key obtained for a service_account to connect
            with Google Drive / Google Spreadsheets API.
        """
        SCOPES = (
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        )
        cred = service_account.Credentials.from_service_account_info(cred, scopes=SCOPES)
        return pygsheets.authorize(custom_credentials=cred)

    @staticmethod
    def gsheet_to_file(
            greader: pygsheets.client.Client,
            fp: str,
            spreadsheet_name: str,
            worksheet_name: str,
            format: str = 'csv'
        ) -> None:
        """Save google sheet to local file.

        Parameters
        ----------
        fp : str
            Filepath of where to save the google sheet.
        spreadsheet_name : str
            Spreadsheet name, in other words the main title of the google sheet.
        worksheet_name : str
            The specific worksheet within the google spreadsheet that is to be saved.
        format : str, optional, default 'csv'
            Type of file to save. Possible values: ['csv', 'ftr'].
        """
        spreadsh = greader.open(spreadsheet_name)
        worksh = spreadsh.worksheet_by_title(worksheet_name)
        df = pd.DataFrame(worksh.get_all_records())
        if format == 'csv':
            df.to_csv(fp, index=False)
        elif format == 'ftr':
            df.reset_index(drop=True).to_feather(fp)
        else:
            raise Exception('format only supports updating ".csv" and ".ftr" files.')

    @staticmethod
    def to_csv(
            df: pd.DataFrame,
            zip_name: str,
            dir: str,
            file_name: Optional[str] = None,
            method: str = 'zip',
            compresslevel: int = 9
        ) -> None:
        """Save dataframe to csv file with compression.

        Parameters
        ----------
        zip_name : str
            Name of the .zip file that the dataframe will be compressed into.
        dir : str
            File path of where to save the .zip.
        file_name : Optional[str], optional, default None
            Name of the file within the .zip file post-extraction. Default of None will have
            the same name as the zip_name.
        method : str, optional, default 'zip'
            Type of compression.
        compresslevel : int, optional, default 9
            Degree of compression where higher number indicates higher compression.
        """
        # Process arguments.
        if dir[-1] == '/':
            dir = dir[:-1]
        if re.search('\.csv', zip_name):
            zip_name = re.sub('\.csv', '', zip_name)
        if file_name is None:
            file_name = zip_name

        compress_param = {
            'archive_name': f'{file_name}.csv',
            'method': method,
            'compresslevel': compresslevel
        }
        df.to_csv(f'{dir}/{zip_name}.zip', compression=compress_param, index=False)

    @staticmethod
    def import_module(module_filepath: str):
        """Import module to a variable from a specific filepath.

        Parameters
        ----------
        module_filepath : str
            Filepath leading to the module.
        """
        module_name = module_filepath.split('/')[-1]
        module_dir = re.sub(module_name, '', module_filepath)
        spec = importlib.util.spec_from_file_location(module_name, f'{module_dir}{module_name}')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def create_yaml_template(input_fp: str, output_fp: str) -> None:
        """Creates empty .yaml template from a .yaml file.

        Useful for converting a filled out environment .yaml file into an empty template for users
        to clone into their directories without seeing anyone else's secrets.
        
        Parameters
        ----------
        input_fp : str
            Filepath to the input .yaml file.
        output_fp : str
            Output filepath of the empty .yaml template.
        """
        with open(input_fp) as fp:
            env = fp.readlines()

        template = []
        for line in env:
            if line == '\n':
                template.append('\n')
            elif re.search('#', line) is not None:
                template.append(line)
            elif re.search(':', line) is None:
                continue
            else:
                if re.search('\[', line) is not None:
                    line = re.sub(':.+', ': []', line)
                else:
                    line = re.sub(':.+', ':', line)
                template.append(line)

        with open(output_fp, 'w') as f:
            f.write(''.join(template))

    @staticmethod
    def run_shell(cmd: str, logger: logging.Logger) -> None:
        """Wrapper around shell command to log any unexpected errors."""
        p = subprocess.run(cmd, capture_output=True, shell=True)
        if p.returncode != 0:
            logger.error(f'{p.args}\n{p.stderr.decode()}')

    class HidePrints:
        """Suppress print statements.
        
        Example use:

        import HidePrints

        def func_with_prints():
            print('jaja')

        with HidePrints():
            # This will not print 'jaja'.
            func_with_prints()
        """
        def __enter__(self):
            self._original_stdout = sys.stdout
            sys.stdout = open(os.devnull, 'w')

        def __exit__(self, exc_type, exc_val, exc_tb):
            sys.stdout.close()
            sys.stdout = self._original_stdout

    @staticmethod
    def read_files(
            dir: str,
            file_type: Literal['csv', 'ftr'] = 'csv',
            period_beg: Optional[Union[str, pd.Timestamp]] = None,
            period_end: Optional[Union[str, pd.Timestamp]] = None,
            add_date: bool = False,
            add_filename: bool = False
        )-> pd.DataFrame:
        """Read in a directory of files as a dataframe.

        Parameters
        ----------
        dir : str
            Directory where all files to be read are located.
        period_beg : Union[str, pd.Timestamp], optional, default False
            Given that each filename contains a date in the format of
            'YYYYmmdd', filter out files with date before period_beg.
            Note that period_beg will be normalized to 00:00:00.
        period_end : Union[str, pd.Timestamp], optional, default False
            Given that each filename contains a date in the format of
            'YYYYmmdd', filter out files with date after period_end.            
            Note that period_end will be normalized to 00:00:00.
        add_date : bool, optional, default False
            Given that each filename contains a date in the format of
            'YYYYmmdd', append a column named `_file_created_at` with
            extracted date from filename.
        add_filename: bool, optional, default False
            Append a column named `_file_name` with extracted filenames.
        """
        if dir[-1] == '/':
            dir = dir[:-1]
        if period_beg:
            period_beg = pd.Timestamp(period_beg).normalize()
        if period_end:
            period_end = pd.Timestamp(period_end).normalize()

        files = []
        filepaths = glob.glob(f'{dir}/*{file_type}')
        if not filepaths:
            raise Exception('No files found in specified directory.')

        for filepath in sorted(filepaths, reverse=True):
            if file_type == 'csv':
                file = pd.read_csv(filepath)
            elif file_type == 'ftr':
                file = pd.read_feather(filepath)
            else:
                raise Exception('Unsupported file_type.')

            file_name = filepath.split('/')[-1]
            if period_beg or period_end or add_date:
                file_date = re.search('\d{8}', file_name).group()
                file_date = pd.Timestamp(file_date).normalize()

            if add_filename:
                filename_col = '_file_name'
                if filename_col in file.columns:
                    raise Exception(f'`{filename_col}` column already exists.')
                file[filename_col] = file_name

            if add_date:
                filedate_col = '_file_created_at'
                if filedate_col in file.columns:
                    raise Exception(f'`{filedate_col}` column already exists.')
                file[filedate_col] = file_date
            
            files.append(file)
        files = pd.concat(files, axis=0, ignore_index=True)

        if period_beg:
            files = files[files['_file_created_at'] >= period_beg].reset_index(drop=True)
        if period_end:
            files = files[files['_file_created_at'] <= period_end].reset_index(drop=True)
        return files

    @staticmethod
    def snake_to_pascal(snake: str) -> str:
        return ''.join([_snake.capitalize() for _snake in snake.split('_')])
