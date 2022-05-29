#!/usr/bin/python3

import argparse
import base64
import bs4
import requests
import sqlalchemy
import sqlalchemy.orm
import sys
from typing import List, Tuple

class InvalidPasswordError(Exception):
    def __str__(self) -> str:
        return 'Invalid credentials provided'

class SessionActiveError(Exception):
    def __str__(self) -> str:
        return 'A session is already active for the specified credentials'


Base = sqlalchemy.orm.declarative_base()


class Question(Base):
    __tablename__ = 'questions'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    text = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    image = sqlalchemy.Column(sqlalchemy.LargeBinary)

    answers = sqlalchemy.orm.relationship('Answer', back_populates='question')

class Answer(Base):
    __tablename__ = 'answers'

    question_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey('questions.id'), nullable=False, primary_key=True)
    number = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    text = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    correct = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False)

    question = sqlalchemy.orm.relationship('Question', back_populates='answers')

class Explanation(Base):
    __tablename__ = 'explanations'

    question_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey('questions.id'), nullable=False, primary_key=True)
    text = sqlalchemy.Column(sqlalchemy.String)


ERRORS = {
    'Neteisingas kodas': InvalidPasswordError,
    'Šis naudotojas jau yra prisijungęs': SessionActiveError,
}


class TestaiKetSession:
    def __init__(self, category: str, password: str=None, cookie: str=None):
        if (not password and not cookie) or (password and cookie):
            raise ValueError('Either a password or a session cookie must be specified')

        self._session = requests.Session()

        if password:
            self._password = password
        if cookie:
            self._session.cookies.set('CMSSESSID520b200f', cookie, domain='www.testaiket.lt')
            self._session.cookies.set('feu_sessionid', cookie, domain='www.testaiket.lt')

    def log_in(self) -> None:
        data = {
            'mact': 'FrontEndUsers,me69c0,do_login,1',
            'me69c0returnid': '56',
            'page': '56',
            'me69c0nocaptcha': '1',
            'me69c0feu_input_password': self._password,
            'me69c0submit': 'pradėti',
        }
        r = self._session.post('http://www.testaiket.lt/', data=data)
        soup = bs4.BeautifulSoup(r.text, features='lxml')
        if (error_message := soup.find('div', class_='errorMessage')):
            for error, exception in ERRORS.items():
                if error in error_message.next_element.strip():
                    raise exception()

        print('Session cookie:', self._session.cookies['CMSSESSID520b200f'])

    def log_out(self) -> None:
        self._session.get('http://www.testaiket.lt/index.php?mact=FrontEndUsers,cntnt01,logout,0&cntnt01returnid=15')

    def scrape(self, session: sqlalchemy.orm.Session, category: str, group: int) -> None:
        r = self._session.get('http://www.testaiket.lt/index.php?mact=Ket,mb7908,default,1&mb7908cat={}&mb7908group={}&mb7908returnid=15&page=15'.format(category, group))
        soup = bs4.BeautifulSoup(r.text, features='lxml')

        for i in range(1, 30 + 1):
            question = soup.find('div', id='question_{}'.format(i), class_='ket_q_cont')
            body = question.find('div', class_='ket_q_body')

            question_id = question.find('input')['value']

            print('Extracting question #{}…'.format(question_id))

            text = body.find('div', class_='pText').text.strip()

            image_container = question.find('div', class_='ket_img')
            image_src = image_container.find('img')['src'] if image_container else None
            if image_src:
                print('Retrieving image…')
                image_r = self._session.get('http://www.testaiket.lt/{}'.format(image_src))
                image = base64.standard_b64encode(image_r.content)
            else:
                image = None

            session.add(Question(id=question_id, text=text, image=image))

            answers = question.find('div', class_='cBackground').find('div', class_='ket_q_answers')
            for answer in answers.find_all('div', class_='ket_answer'):
                number = answer['id'].rsplit('_', maxsplit=1)[-1]
                text = answer.find('table').find('tr').find('td', class_='tdTable3').text
                correct = answers.find('input', id='cb_{}_{}_correct'.format(i, number))['value'] == '1'

                session.add(Answer(question_id=question_id, number=number, text=text, correct=correct))

            text = body.find('div', class_='ket_q_body2').renderContents().decode().strip()

            session.add(Explanation(question_id=question_id, text=text or None))

        print('Committing to database…')

        session.commit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('--category', type=str, choices=['A', 'B', 'C', 'CE', 'D'], required=True, help='Set license category')
    parser.add_argument('--database-path', type=str, default='sqlite:///ket.db', help='Set alternate path to the database')
    parser.add_argument('--debug', action='store_true', help='Enable SQLAlchemy debug logging')
    # XXX: I forgot what this is…
    parser.add_argument('--group', type=int, default=0, help='')

    group = parser.add_mutually_exclusive_group()

    group.add_argument('--cookie', type=str, help='Authenticate using browser cookie')
    group.add_argument('--password', type=str, help='Authenticate using password')

    args = parser.parse_args()
    engine = sqlalchemy.create_engine(args.database_path, echo=args.debug, future=True)
    sa_session = sqlalchemy.orm.Session(engine, future=True)
    session = TestaiKetSession(args.category, password=args.password, cookie=args.cookie)

    if not args.cookie:
        print('Logging in…')
        session.log_in()

    try:
        questions = session.scrape(sa_session, args.category, args.group)
    except Exception as ex:
        print('Logging out…')
        session.log_out()

        raise

    print('Logging out…')
    session.log_out()
