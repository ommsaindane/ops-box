#!/usr/bin/env python3

from calculator import add, subtract, multiply, divide

if __name__ == '__main__':
    print('Calculator is running...')
    while True:
        operation = input('Enter operation (add, subtract, multiply, divide) or type exit to quit: ')
        if operation.lower() == 'exit':
            break
        num1 = float(input('Enter first number: '))
        num2 = float(input('Enter second number: '))
        if operation.lower() == 'add':
            print(f'Result: {add(num1, num2)}')
        elif operation.lower() == 'subtract':
            print(f'Result: {subtract(num1, num2)}')
        elif operation.lower() == 'multiply':
            print(f'Result: {multiply(num1, num2)}')
        elif operation.lower() == 'divide':
            try:
                print(f'Result: {divide(num1, num2)}')
            except ValueError as e:
                print(e)