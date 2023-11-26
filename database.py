import datetime

import sqlalchemy
from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Integer, String, DateTime, func, and_
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session, relationship
from sqlalchemy.exc import DatabaseError
import sqlalchemy as sa
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin


class DatabaseExitException(Exception):
    """
    Базовая ошибка, выбрасываемая функциями файла.
    """
    pass


def _raises_database_exit_exception(func):
    """
    Декоратор для внутренних функций, преобразующий DatabaseError в DatabaseExitException.
    :param func: Декорируемая функция.
    """

    def _wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except DatabaseError as e:
            raise DatabaseExitException(f"Невозможно получить данные из БД:\n{e}")

    return _wrapper

    # TODO: add exception handling


class Base(DeclarativeBase):
    pass


class Interest(Base):
    __tablename__ = "Interest"

    id = sa.Column(Integer, primary_key=True)
    name = sa.Column(String(64), index=True, unique=True, nullable=False)

    def __repr__(self):
        return "<Interest '{}'>".format(self.name)


class User(UserMixin, Base):
    __tablename__ = "User"

    id = sa.Column(Integer, primary_key=True)
    nickname = sa.Column(String(64), index=True, unique=True, nullable=False)
    birth_date = sa.Column(DateTime, index=True)
    about = sa.Column(String(500), index=True)
    email = sa.Column(String(120), index=True, unique=True, nullable=False)
    interests = relationship('Interest', secondary='user_interest', backref='User')
    password_hash = sa.Column(String(128))

    # TODO: Check, why it doesn't work (+ fix m2m)
    # friends = relationship('User', secondary='user_friend', backref='User')
    # potential_friends = relationship('User', secondary='user_potential_friend', backref='User')
    # friendship_applications = relationship('User', secondary='user_friendship_application', backref='User')

    def __repr__(self):
        return '<User {}>'.format(self.nickname)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class UserDatabase:

    def __init__(self):
        self.app = Flask(__name__)
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///user.db"
        self.db = SQLAlchemy(model_class=Base)
        self.db.init_app(self.app)
        self.user_interest_m2m = self.db.Table(
            "user_interest",
            sa.Column("user_id", sa.ForeignKey('User.id'), primary_key=True),
            sa.Column("interest_id", sa.ForeignKey('Interest.id'), primary_key=True)
        )
        self.user_user_m2m_friend = self.db.Table(
            "user_friend",
            sa.Column("user_id", sa.ForeignKey('User.id'), primary_key=True),
            sa.Column("friend_id", sa.ForeignKey('User.id'), primary_key=True)
        )
        self.user_user_m2m_potential_friend = self.db.Table(
            "user_potential_friend",
            sa.Column("user_id", sa.ForeignKey('User.id'), primary_key=True),
            sa.Column("potential_friend_id", sa.ForeignKey('User.id'), primary_key=True)
        )
        self.user_user_m2m_friendship_application = self.db.Table(
            "user_friendship_application",
            sa.Column("user_id", sa.ForeignKey('User.id'), primary_key=True),
            sa.Column("potential_friend_id", sa.ForeignKey('User.id'), primary_key=True)
        )

    # TODO: check why foreign keys work so bad

    @_raises_database_exit_exception
    def create_tables(self) -> None:
        with self.app.app_context():
            self.db.create_all()

    @_raises_database_exit_exception
    def drop_tables(self) -> None:
        with self.app.app_context():
            self.db.drop_all()

    @_raises_database_exit_exception
    def create_user(self, id: int, nickname: str, email: str, birth_date: datetime.datetime, about: str,
                    password: str) -> None:
        with self.app.app_context():
            user = User()
            user.id = id
            user.nickname = nickname
            user.about = about
            user.set_password(password)
            user.email = email
            user.birth_date = birth_date
            self.db.session.add(user)
            self.db.session.commit()

    @_raises_database_exit_exception
    def add_tag(self, id: int, name: str) -> None:
        with self.app.app_context():
            interest = Interest(id=id, name=name)
            self.db.session.add(interest)
            self.db.session.commit()

    @_raises_database_exit_exception
    def add_user_tag(self, user_id: int, interest_id: int) -> None:
        with self.app.app_context():
            self.db.session.execute(sa.insert(self.user_interest_m2m).values(user_id=user_id, interest_id=interest_id))
            self.db.session.commit()

    @_raises_database_exit_exception
    def delete_user_tag(self, user_id: int, interest_id: int) -> None:
        with self.app.app_context():
            self.db.session.execute(sa.delete(self.user_interest_m2m).where(and_(
                self.user_interest_m2m.c.user_id == user_id, self.user_interest_m2m.c.interest_id == interest_id)))
            self.db.session.commit()

    @_raises_database_exit_exception
    def delete_user(self, user_id: int) -> None:
        with self.app.app_context():
            self.clear_user_tags(user_id)
            self.db.session.query(User).filter_by(id=user_id).delete()
            self.db.session.commit()

    @_raises_database_exit_exception
    def delete_tag(self, interest_id: int) -> None:
        with self.app.app_context():
            self.db.session.execute(
                sa.delete(self.user_interest_m2m).where(self.user_interest_m2m.c.interest_id == interest_id))
            self.db.session.query(Interest).filter_by(id=interest_id).delete()
            self.db.session.commit()

    @_raises_database_exit_exception
    def get_user_by_index_or_none(self, user_id: int) -> User:
        with self.app.app_context():
            user = self.db.session.query(User).get(user_id)
            return user

    @_raises_database_exit_exception
    def get_user_tags_by_name(self, nickname: str) -> User:
        with self.app.app_context():
            user = self.db.session.query(User).filter_by(nickname=nickname).first()
            return user

    @_raises_database_exit_exception
    def get_user_by_email_or_none(self, email: str) -> User:
        with self.app.app_context():
            user = self.db.session.query(User).filter_by(email=email).first()
            return user

    @_raises_database_exit_exception
    def get_tag_by_index_or_none(self, interest_id: int) -> Interest:
        with self.app.app_context():
            interest = self.db.session.query(Interest).filter_by(id=interest_id).first()
            return interest

    @_raises_database_exit_exception
    def get_tag_by_name_or_none(self, name: str) -> Interest:
        with self.app.app_context():
            interest = self.db.session.query(Interest).filter_by(name=name).first()
            return interest

    @_raises_database_exit_exception
    def get_count_of_users(self) -> int:
        with self.app.app_context():
            return self.db.session.query(User).count()

    @_raises_database_exit_exception
    def get_count_of_tags(self) -> int:
        with self.app.app_context():
            return self.db.session.query(Interest).count()

    @_raises_database_exit_exception
    def get_users(self) -> [User]:
        with self.app.app_context():
            return self.db.session.query(User).all()

    @_raises_database_exit_exception
    def get_tags(self) -> [Interest]:
        with self.app.app_context():
            return self.db.session.query(Interest).all()

    @_raises_database_exit_exception
    def get_user_tags(self, user_id: int) -> [Interest]:
        with self.app.app_context():
            select = self.db.session.execute(
                sa.select(self.user_interest_m2m.c.interest_id).where(
                    self.user_interest_m2m.c.user_id == user_id)).fetchall()
            interests = []
            for interest_id in select:
                interests.append(self.db.session.query(Interest).filter_by(id=interest_id[0]).first())
            return interests

    @_raises_database_exit_exception
    def get_users_with_tag(self, interest_id: int) -> [User]:
        with self.app.app_context():
            select = self.db.session.execute(
                sa.select(self.user_interest_m2m.c.user_id).where(
                    self.user_interest_m2m.c.interest_id == interest_id)).fetchall()
            users = []
            for user_id in select:
                users.append(self.db.session.query(User).filter_by(id=user_id[0]).first())
            return users

    @_raises_database_exit_exception
    def clear_user_tags(self, user_id: int) -> None:
        with self.app.app_context():
            self.db.session.execute(
                sa.delete(self.user_interest_m2m).where(self.user_interest_m2m.c.user_id == user_id))
            self.db.session.commit()

    @_raises_database_exit_exception
    def has_user(self, email: str, password: str) -> bool:
        with self.app.app_context():
            user = self.get_user_by_email_or_none(email)
            if user is None:
                return False
            return user.check_password(password)

    @_raises_database_exit_exception
    def has_tag(self, tag: str) -> bool:
        with self.app.app_context():
            return tag in list(map(lambda x: x.name, self.db.session.query(Interest).all()))

    @_raises_database_exit_exception
    def set_to_user_with_id(self, user_id: int, nickname: str, email: str, birth_date: datetime.datetime,
                            about: str, password: str) -> None:
        with self.app.app_context():
            self.db.session.query(User).filter_by(id=user_id).update({
                'nickname': nickname,
                'email': email,
                'birth_date': birth_date,
                'about': about,
                'password_hash': generate_password_hash(password)
            }, synchronize_session=False)
            self.db.session.commit()

    # friends part
    @_raises_database_exit_exception
    def add_friend(self, user_id: int, friend_id: int) -> None:
        with self.app.app_context():
            self.db.session.execute(sa.insert(self.user_user_m2m_friend).values(user_id=user_id, friend_id=friend_id))
            self.db.session.execute(sa.insert(self.user_user_m2m_friend).values(user_id=friend_id, friend_id=user_id))
            self.db.session.commit()

    @_raises_database_exit_exception
    def remove_friend(self, user_id: int, friend_id: int) -> None:
        with self.app.app_context():
            self.db.session.execute(sa.delete(self.user_user_m2m_friend).where(and_(
                self.user_user_m2m_friend.c.user_id == user_id, self.user_user_m2m_friend.c.friend_id == friend_id)))
            self.db.session.execute(sa.delete(self.user_user_m2m_friend).where(and_(
                self.user_user_m2m_friend.c.user_id == friend_id, self.user_user_m2m_friend.c.friend_id == user_id)))
            self.db.session.commit()

    @_raises_database_exit_exception
    def get_friends(self, user_id: int) -> [User]:
        with self.app.app_context():
            select = self.db.session.execute(
                sa.select(self.user_user_m2m_friend.c.friend_id).where(
                    self.user_user_m2m_friend.c.user_id == user_id)).fetchall()
            friends = []
            for friend_id in select:
                friends.append(self.db.session.query(User).filter_by(id=friend_id[0]).first())
            return friends

    @_raises_database_exit_exception
    def is_friend(self, user_id: int, friend_id: int) -> bool:
        with self.app.app_context():
            friends = self.get_friends(user_id)
            return friend_id in list(map(lambda x: x.id, friends))

    # potential friends part

    @_raises_database_exit_exception
    def add_potential_friend(self, user_id: int, potential_friend_id: int) -> None:
        with self.app.app_context():
            self.db.session.execute(
                sa.insert(self.user_user_m2m_potential_friend).values(user_id=user_id,
                                                                      potential_friend_id=potential_friend_id))
            self.db.session.commit()

    @_raises_database_exit_exception
    def remove_potential_friend(self, user_id: int, potential_friend_id: int) -> None:
        with self.app.app_context():
            self.db.session.execute(sa.delete(self.user_user_m2m_potential_friend).where(and_(
                self.user_user_m2m_potential_friend.c.user_id == user_id,
                self.user_user_m2m_potential_friend.c.potential_friend_id == potential_friend_id)))
            self.db.session.commit()

    @_raises_database_exit_exception
    def get_potential_friends(self, user_id: int) -> [User]:
        with self.app.app_context():
            select = self.db.session.execute(
                sa.select(self.user_user_m2m_potential_friend.c.potential_friend_id).where(
                    self.user_user_m2m_potential_friend.c.user_id == user_id)).fetchall()
            friends = []
            for friend_id in select:
                friends.append(self.db.session.query(User).filter_by(id=friend_id[0]).first())
            return friends

    @_raises_database_exit_exception
    def is_potential_friend(self, user_id: int, potential_friend_id: int) -> bool:
        with self.app.app_context():
            friends = self.get_potential_friends(user_id)
            return potential_friend_id in list(map(lambda x: x.id, friends))

    # friendship application part

    @_raises_database_exit_exception
    def add_application(self, user_id: int, potential_friend_id: int) -> None:
        with self.app.app_context():
            self.db.session.execute(
                sa.insert(self.user_user_m2m_friendship_application).values(user_id=user_id,
                                                                      potential_friend_id=potential_friend_id))
            self.db.session.commit()

    @_raises_database_exit_exception
    def remove_application(self, user_id: int, potential_friend_id: int) -> None:
        with self.app.app_context():
            self.db.session.execute(sa.delete(self.user_user_m2m_friendship_application).where(and_(
                self.user_user_m2m_friendship_application.c.user_id == user_id,
                self.user_user_m2m_friendship_application.c.potential_friend_id == potential_friend_id)))
            self.db.session.commit()

    @_raises_database_exit_exception
    def get_applications(self, user_id: int) -> [User]:
        with self.app.app_context():
            select = self.db.session.execute(
                sa.select(self.user_user_m2m_friendship_application.c.potential_friend_id).where(
                    self.user_user_m2m_friendship_application.c.user_id == user_id)).fetchall()
            friends = []
            for friend_id in select:
                friends.append(self.db.session.query(User).filter_by(id=friend_id[0]).first())
            return friends

    @_raises_database_exit_exception
    def has_application(self, user_id: int, potential_friend_id: int) -> bool:
        with self.app.app_context():
            friends = self.get_applications(user_id)
            return potential_friend_id in list(map(lambda x: x.id, friends))
