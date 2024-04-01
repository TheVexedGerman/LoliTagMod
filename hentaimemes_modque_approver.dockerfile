FROM python:3.11-bookworm

WORKDIR /home/python

RUN git clone --recurse-submodules https://github.com/TheVexedGerman/LoliTagMod.git .

RUN pip install --no-cache-dir -r requirements.txt
COPY praw.ini postgres_credentials_modque.py hentaimemes_modque_approver.sh ./
COPY wrapper/postgres_credentials.py wrapper/

CMD [ "bash", "/home/python/hentaimemes_modque_approver.sh"]