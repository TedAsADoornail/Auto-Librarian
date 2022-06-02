import yagmail

user = 'autolibrarian@gmail.com'
app_password = 'pfkxveangjvqabyo'
to = 'teddyd93_Rkc6lB@kindle.com'


def send_book_to_kindle_email(file_name):
    subject = file_name
    content = [file_name, 'books/' + file_name]

    with yagmail.SMTP(user, app_password) as yag:
        yag.send(to, subject, content)
        print('Sent email successfully')
        return 1
