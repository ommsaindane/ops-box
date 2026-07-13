# This is a Python calculator

from calculator import add, subtract, multiply, divide
def main():
    print('1. Add')
    print('2. Subtract')
    print('3. Multiply')
    print('4. Divide')
    choice = input('Enter your choice(1/2/3/4): ')
    if choice == '1':
        num1 = float(input('Enter first number: '))
        num2 = float(input('Enter second number: '))
        print(f'The result is {add(num1, num2)}')
    elif choice == '2':
        num1 = float(input('Enter first number: '))
        num2 = float(input('Enter second number: '))
        print(f'The result is {subtract(num1, num2)}')
    elif choice == '3':
        num1 = float(input('Enter first number: '))
        num2 = float(input('Enter second number: '))
        print(f'The result is {multiply(num1, num2)}')
    elif choice == '4':
        num1 = float(input('Enter first number: '))
        num2 = float(input('Enter second number: '))
        print(f'The result is {divide(num1, num2)}')
    else:
        print('Invalid Input')