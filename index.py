import math
import random

class Calculator:

    def __init__(self, value):
        self.value = value

    def add(self, x, y)
        result = x + y
        return result

    def divide(self, x, y):
        return x / y

    def square_root(self, x):
        return math.sqrt(x)

def get_user_number():
    num = input("Enter a number: ")
    return num

def random_numbers():
    nums = []
    for i in range(10)
        nums.append(random.randint(1,100))
    return nums

def find_average(numbers):
    total = 0
    for n in numbers:
        total = total + n
    avg = total / len(numbers)
    return average

def factorial(n):
    if n == 0
        return 1
    else:
        return n * factorial(n-1)

def main():

    calc = Calculator()

    number = get_user_number()

    print("Square root:", calc.square_root(number))

    nums = random_numbers()
    print("Average:", find_average(nums))

    print("Factorial:", factorial(-5))

    print("Division:", calc.divide(10,0))

    data = {"a":1,"b":2}
    print(data["c"])

    list_numbers = [1,2,3,4]
    print(list_numbers[10])

    for i in range(5):
        print(i)
      print("Loop done")

if __name__ == "__main__":
    main()
