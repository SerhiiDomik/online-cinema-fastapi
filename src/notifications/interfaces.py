from abc import ABC, abstractmethod


class EmailSenderInterface(ABC):

    @abstractmethod
    async def send_activation_email(self, email: str, activation_link: str) -> None:
        pass

    @abstractmethod
    async def send_activation_complete_email(self, email: str, login_link: str) -> None:
        pass

    @abstractmethod
    async def send_password_reset_email(self, email: str, reset_link: str) -> None:
        pass

    @abstractmethod
    async def send_password_reset_complete_email(
        self, email: str, login_link: str
    ) -> None:
        pass

    @abstractmethod
    async def send_comment_reaction_notification(
        self,
        email: str,
        reacting_user_email: str,
        reaction_type: str,
        comment_content: str,
    ) -> None:
        pass

    @abstractmethod
    async def send_comment_reply_notification(
        self,
        email: str,
        replying_user_email: str,
        parent_comment_content: str,
        reply_content: str,
    ) -> None:
        pass
