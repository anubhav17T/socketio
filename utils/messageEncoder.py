import base64

from pybase24 import encode24

LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'


# steps for translation = 1. converting userId into base 24 and using base24 userId encrypting message and
# after that completly encoding message into base64F

def translateMessage(userId, message, mode):
    translated = []
    keyIndex = 0
    userId = userId*4
    key = encode24(userId.encode()).upper()
    if mode == 'decrypt':
        base64_bytes = str(message).encode("ascii")
        sample_string_bytes = base64.b64decode(base64_bytes)
        message = sample_string_bytes.decode("ascii")

    for symbol in message:
        num = LETTERS.find(symbol.upper())
        if num != -1:
            if mode == 'encrypt':
                num += LETTERS.find(key[keyIndex])
            elif mode == 'decrypt':
                num -= LETTERS.find(key[keyIndex])
            num %= len(LETTERS)

            if symbol.isupper():
                translated.append(LETTERS[num])
            elif symbol.islower():
                translated.append(LETTERS[num].lower())
            keyIndex += 1

            if keyIndex == len(key):
                keyIndex = 0
        else:
            translated.append(symbol)
    complete_messages = ''.join(translated)
    if mode == 'encrypt':
        sample_string_bytes = complete_messages.encode("ascii")
        base64_bytes = base64.b64encode(sample_string_bytes)
        complete_messages = base64_bytes.decode("ascii")
    return complete_messages