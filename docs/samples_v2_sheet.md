# Review sheet: samples_v2.jsonl (67 mutants)

### Mbpp/751#off_by_one (bug line 7)

Write a function to check if the given array represents min heap or not. https://www.geeksforgeeks.org/how-to-check-if-a-given-array-represents-a-binary-heap/
assert check_min_heap([1, 2, 3, 4, 5, 6]) == True

```diff
@@ -6,3 +6,3 @@
     right_child = (2 * i + 2 == len(arr)) or  \
-                (arr[i] <= arr[2 * i + 2] and \
+                (arr[i] <= arr[2 * i + 2 - 1] and \
                  check_min_heap_helper(arr, 2 * i + 2))
```

First failing MBPP+ input:

```
input [[3, 4, 5, 6, 7, 8, 9, 6, 5]]
expected False
got True
```

class: 

### Mbpp/166#wrong_return (bug line 4)

Write a function that counts the number of pairs of integers in a list that xor to an even number.
assert find_even_pair([5, 4, 7, 2, 1]) == 4

```diff
@@ -3,3 +3,3 @@
   if len(A) < 2: 
-    return 0
+    return 1
   return sum((a ^ b) % 2 == 0 for i, a in enumerate(A) for b in A[i + 1:])
```

First failing MBPP+ input:

```
input [[]]
expected 0
got 1
```

class: 

### Mbpp/137#remove_branch (bug line 3)

Write a function to find the ratio of zeroes to non-zeroes in an array of integers.
assert math.isclose(zero_count([0, 1, 2, -1, -5, 6, 0, -3, -2, 3, 4, 6, 8]), 0.181818, rel_tol=0.001)

```diff
@@ -2,4 +2,2 @@
 def zero_count(nums):
-    if all(x == 0 for x in nums):
-        return float('inf')
     return sum(x == 0 for x in nums) / sum(x != 0 for x in nums)
```

First failing MBPP+ input:

```
input [[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]]
expected inf
got 'ZeroDivisionError: division by zero'
```

class: 

### Mbpp/260#wrong_return (bug line 4)

Write a function to find the nth newman–shanks–williams prime number.
assert newman_prime(3) == 7

```diff
@@ -3,3 +3,3 @@
 	if n == 0 or n == 1: 
-		return 1
+		return 0
 	a = 1
```

First failing MBPP+ input:

```
input [0]
expected 1
got 0
```

class: 

### Mbpp/784#arith_op (bug line 5)

Write a function to find the product of first even and odd number of a given list.
assert mul_even_odd([1,3,5,7,4,1,6,8])==4

```diff
@@ -4,2 +4,2 @@
     first_odd = next((el for el in list1 if el%2!=0),-1)
-    return (first_even*first_odd)
+    return (first_even//first_odd)
```

First failing MBPP+ input:

```
input [[-10, -5, 0, 5, 10]]
expected 50
got 2
```

class: 

### Mbpp/245#comparison_flip (bug line 11)

Write a function that takes an array and finds the maximum sum of a bitonic subsequence for the given array, where a sequence is bitonic if it is first increasing and then decreasing.
assert max_sum([1, 15, 51, 45, 33, 100, 12, 18, 9]) == 194

```diff
@@ -10,3 +10,3 @@
 		for j in range(1, i): 
-			if arr[-i] > arr[-j] and MSDBS[-i] < MSDBS[-j] + arr[-i]: 
+			if arr[-i] >= arr[-j] and MSDBS[-i] < MSDBS[-j] + arr[-i]: 
 				MSDBS[-i] = MSDBS[-j] + arr[-i] 
```

First failing MBPP+ input:

```
input [[10, 9, 8, 7, 6, 5, 4, 4, 3, 2, 1]]
expected 55
got 59
```

class: 

### Mbpp/306#off_by_one (bug line 15)

Write a function to find the maximum sum of increasing subsequence from prefix until ith index and also including a given kth element which is after i, i.e., k > i .
assert max_sum_increasing_subseq([1, 101, 2, 3, 100, 4, 5 ], 7, 4, 6) == 11

```diff
@@ -14,3 +14,3 @@
 				else:
-					dp[i][j] = dp[i - 1][j]
+					dp[i][j] = dp[i - 1 + 1][j]
 			else:
```

First failing MBPP+ input:

```
input [[5, 2, 4, 1, 3, 6], 6, 1, 5]
expected 11
got 0
```

class: 

### Mbpp/162#wrong_return (bug line 4)

Write a function to calculate the sum (n - 2*i) from i=0 to n // 2, for instance n + (n-2) + (n-4)... (until n-x =< 0).
assert sum_series(6) == 12

```diff
@@ -3,3 +3,3 @@
   if n <= 0:
-    return 0
+    return 1
   return sum(n - 2 * i for i in range(n // 2 + 1))
```

First failing MBPP+ input:

```
input [0]
expected 0
got 1
```

class: 

### Mbpp/239#off_by_one (bug line 9)

Write a function that takes in positive integers m and n and finds the number of possible sequences of length n, such that each element is a positive integer and is greater than or equal to twice the previous element but less than or equal to m.
assert get_total_number_of_sequences(10, 4) == 4

```diff
@@ -8,3 +8,3 @@
 			elif i<j: 
-				T[i][j] = 0
+				T[i + 1][j] = 0
 			elif j==1: 
```

First failing MBPP+ input:

```
input [5, 6]
expected 0
got 'IndexError: list index out of range'
```

class: 

### Mbpp/100#arith_op (bug line 32)

Write a function to find the next smallest palindrome of a specified integer, returned as an integer.
assert next_smallest_palindrome(99)==101

```diff
@@ -31,3 +31,3 @@
                 num[mid] %= 10
-                j = mid + 1
+                j = mid - 1
             else:
```

First failing MBPP+ input:

```
input [45678]
expected 45754
got 45454
```

class: 

### Mbpp/222#off_by_one (bug line 3)

Write a function to check if all the elements in tuple have same data type or not.
assert check_type((5, 6, 7, 3, 5, 6) ) == True

```diff
@@ -2,2 +2,2 @@
 def check_type(test_tuple):
-    return all(isinstance(item, type(test_tuple[0])) for item in test_tuple)
+    return all(isinstance(item, type(test_tuple[1])) for item in test_tuple)
```

First failing MBPP+ input:

```
input [([[1, 2, 3]],)]
expected True
got 'IndexError: tuple index out of range'
```

class: 

### Mbpp/68#off_by_one (bug line 3)

Write a python function to check whether the given array is monotonic or not.
assert is_Monotonic([6, 5, 4, 4]) == True

```diff
@@ -2,2 +2,2 @@
 def is_Monotonic(A): 
-    return all(a <= b for a, b in zip(A, A[1:])) or all(a >= b for a, b in zip(A, A[1:]))
+    return all(a <= b for a, b in zip(A, A[1:])) or all(a >= b for a, b in zip(A, A[2:]))
```

First failing MBPP+ input:

```
input [[43.01465662466188, -69.38224302373561, -10.481407073259263]]
expected False
got True
```

class: 

### Mbpp/605#comparison_flip (bug line 4)

Write a function to check if the given integer is a prime number.
assert prime_num(13)==True

```diff
@@ -3,3 +3,3 @@
 def prime_num(num):
-  if num <= 1:
+  if num < 1:
     return False
```

First failing MBPP+ input:

```
input [1]
expected False
got True
```

class: 

### Mbpp/721#arith_op (bug line 9)

Given a square matrix of size N*N given as a list of lists, where each cell is associated with a specific cost. A path is defined as a specific sequence of cells that starts from the top-left cell move only right or down and ends on bottom right cell. We want to find a path with the maximum average over all existing paths. Average is computed as total cost divided by the number of cells visited in the path.
assert maxAverageOfPath([[1, 2, 3], [6, 5, 4], [7, 3, 9]]) == 5.2

```diff
@@ -8,3 +8,3 @@
   for j in range(1, N):
-    dp[0][j] = dp[0][j - 1] + cost[0][j]
+    dp[0][j] = dp[0][j - 1] - cost[0][j]
   for i in range(1, N):
```

First failing MBPP+ input:

```
input [[[0, 1, 0], [0, 0, -1], [0, 0, -1]]]
expected 0.0
got -0.2
```

class: 

### Mbpp/448#remove_branch (bug line 8)

Write a function to calculate the sum of perrin numbers.
assert cal_sum(9) == 49

```diff
@@ -6,4 +6,2 @@
 	if (n == 0): 
-		return 3
-	if (n == 1): 
 		return 3
```

First failing MBPP+ input:

```
input [True]
expected 3
got 5
```

class: 

### Mbpp/129#remove_branch (bug line 8)

Write a function to calculate whether the matrix is a magic square.
assert magic_square_test([[7, 12, 1, 14], [2, 13, 8, 11], [16, 3, 10, 5], [9, 6, 15, 4]])==True

```diff
@@ -7,4 +7,2 @@
     # column
-    if any(sum(row[i] for row in my_matrix) != s for i in range(len(my_matrix[0]))):
-        return False
     # diagonal
```

First failing MBPP+ input:

```
input [[[7, 12, 1, 14], [7, 12, 1, 14], [7, 12, 1, 14], [7, 12, 1, 14]]]
expected False
got True
```

class: 

### Mbpp/84#bool_op (bug line 3)

Write a function to find the nth number in the newman conway sequence.
assert sequence(10) == 6

```diff
@@ -2,3 +2,3 @@
 def sequence(n): 
-	if n == 1 or n == 2: 
+	if n == 1 and n == 2: 
 		return 1
```

First failing MBPP+ input:

```
input [True]
expected 1
got 'IndexError: list assignment index out of range'
```

class: 

### Mbpp/290#off_by_one (bug line 3)

Write a function to find the list of maximum length in a list of lists.
assert max_length([[0], [1, 3], [5, 7], [9, 11], [13, 15, 17]])==(3, [13, 15, 17])

```diff
@@ -2,2 +2,2 @@
 def max_length(list1):
-    return max([(len(x), x) for x in list1], key=lambda x: x[0])
+    return max([(len(x), x) for x in list1], key=lambda x: x[-1])
```

First failing MBPP+ input:

```
input [[[1, 3, 5, 7, 9, 11], [2, 4, 6], [10, 12, 14, 16, 18, 20], [13, 15, 17, 19, 21]]]
expected (6, [1, 3, 5, 7, 9, 11])
got (5, [13, 15, 17, 19, 21])
```

class: 

### Mbpp/436#comparison_flip (bug line 3)

Write a python function to return the negative numbers in a list.
assert neg_nos([-1,4,5,-6]) == [-1,-6]

```diff
@@ -2,2 +2,2 @@
 def neg_nos(list1):
-  return [i for i in list1 if i < 0]
+  return [i for i in list1 if i <= 0]
```

First failing MBPP+ input:

```
input [[1, -2, 0, -5, 7, -8, 10, 12, 0, -15, 18]]
expected [-2, -5, -8, -15]
got [-2, 0, -5, -8, 0, -15]
```

class: 

### Mbpp/745#off_by_one (bug line 3)

Write a function to find numbers within a given range from startnum ti endnum where every number is divisible by every digit it contains. https://www.w3resource.com/python-exercises/lambda/python-lambda-exercise-24.php
assert divisible_by_digits(1,22)==[1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 15, 22]

```diff
@@ -2,3 +2,3 @@
 def divisible_by_digits(startnum, endnum):
-    return [n for n in range(startnum, endnum+1) \
+    return [n for n in range(startnum, endnum+1 + 1) \
                 if not any(map(lambda x: int(x) == 0 or n%int(x) != 0, str(n)))]
```

First failing MBPP+ input:

```
input [599, 998]
expected [612, 624, 636, 648, 666, 672, 728, 735, 777, 784, 816, 824, 848, 864, 888, 936]
got [612, 624, 636, 648, 666, 672, 728, 735, 777, 784, 816, 824, 848, 864, 888, 936, 999]
```

class: 

### Mbpp/763#off_by_one (bug line 5)

Write a python function to find the minimum difference between any two elements in a given array. https://www.geeksforgeeks.org/find-minimum-difference-pair/
assert find_min_diff((1,5,3,19,18,25),6) == 1

```diff
@@ -4,3 +4,3 @@
     diff = 10**20 
-    for i in range(n-1): 
+    for i in range(n-1 - 1): 
         if arr[i+1] - arr[i] < diff: 
```

First failing MBPP+ input:

```
input [(15, 12, 20, 30, 8, 4, 19, 37, 22, 28, 11, 37), 12]
expected 0
got 1
```

class: 

### Mbpp/256#off_by_one (bug line 3)

Write a python function that takes in a non-negative number and returns the number of prime numbers less than the given non-negative number.
assert count_Primes_nums(5) == 2

```diff
@@ -2,2 +2,2 @@
 def count_Primes_nums(n):
-    return sum(all(i % j != 0 for j in range(2, i)) for i in range(2, n))
+    return sum(all(i % j != 0 for j in range(2, i)) for i in range(2, n - 1))
```

First failing MBPP+ input:

```
input [998]
expected 168
got 167
```

class: 

### Mbpp/722#off_by_one (bug line 3)

The input is given as - a dictionary with a student name as a key and a tuple of float (student_height, student_weight) as a value, - minimal height, - minimal weight. Write a function to filter students that have height and weight above the minimum.
assert filter_data({'Cierra Vega': (6.2, 70), 'Alden Cantrell': (5.9, 65), 'Kierra Gentry': (6.0, 68), 'Pierre Cox': (5.8, 66)},6.0,70)=={'Cierra Vega': (6.2, 70)}

```diff
@@ -2,2 +2,2 @@
 def filter_data(students,h,w):
-    return {k: s for k, s in students.items() if s[0] >= h and s[1] >= w}
+    return {k: s for k, s in students.items() if s[-1] >= h and s[1] >= w}
```

First failing MBPP+ input:

```
input [{'Alice': (5.6, 60), 'Bob': (6.1, 70), 'Charlie': (5.9, 65), 'Dave': (5.11, 72)}, 5.8, 67]
expected {'Bob': (6.1, 70)}
got {'Bob': (6.1, 70), 'Dave': (5.11, 72)}
```

class: 

### Mbpp/782#off_by_one (bug line 8)

Write a python function to find the sum of all odd length subarrays. https://www.geeksforgeeks.org/sum-of-all-odd-length-subarrays/
assert odd_length_sum([1,2,4]) == 14

```diff
@@ -7,3 +7,3 @@
         times = ((i + 1) * (n - i) + 1) // 2
-        sum_ += arr[i] * times
+        sum_ += arr[i - 1] * times
     return sum_
```

First failing MBPP+ input:

```
input [[4, 3, 2, 1, 9, 10, 7]]
expected 218
got 194
```

class: 

### Mbpp/620#off_by_one (bug line 9)

Write a function to find the size of the largest subset of a list of numbers so that every pair is divisible.
assert largest_subset([ 1, 3, 6, 13, 17, 18 ]) == 4

```diff
@@ -8,3 +8,3 @@
 		for j in range(i + 1, n):
-			if a[j] % a[i] == 0 or a[i] % a[j] == 0:
+			if a[j] % a[i] == 0 or a[i - 1] % a[j] == 0:
 				mxm = max(mxm, dp[j])
```

First failing MBPP+ input:

```
input [[2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]]
expected 4
got 5
```

class: 

### Mbpp/300#off_by_one (bug line 5)

Write a function to find the count of all binary sequences of length 2n such that sum of first n bits is same as sum of last n bits.
assert math.isclose(count_binary_seq(1), 2.0, rel_tol=0.001)

```diff
@@ -4,3 +4,3 @@
 	res = 1
-	for r in range(1, n + 1): 
+	for r in range(1, n + 1 + 1): 
 		nCr = (nCr * (n + 1 - r)) / r 
```

First failing MBPP+ input:

```
input [1000000]
expected inf
got nan
```

class: 

### Mbpp/567#comparison_flip (bug line 3)

Write a function to check whether a specified list is sorted or not.
assert issort_list([1,2,4,6,8,10,12,14,16,17])==True

```diff
@@ -2,2 +2,2 @@
 def issort_list(list1):
-    return all(a <= b for a, b in zip(list1, list1[1:]))
+    return all(a < b for a, b in zip(list1, list1[1:]))
```

First failing MBPP+ input:

```
input [[1, 2, 4, 4, 6, 8, 10, 10, 12, 12]]
expected True
got False
```

class: 

### Mbpp/3#remove_branch (bug line 4)

Write a python function to identify non-prime numbers.
assert is_not_prime(2) == False

```diff
@@ -3,4 +3,2 @@
 def is_not_prime(n):
-    if n == 1:
-        return True
     for i in range(2, int(math.sqrt(n))+1):
```

First failing MBPP+ input:

```
input [1]
expected True
got False
```

class: 

### Mbpp/809#comparison_flip (bug line 3)

Write a function to check if each element of second tuple is smaller than its corresponding element in the first tuple.
assert check_smaller((1, 2, 3), (2, 3, 4)) == False

```diff
@@ -2,2 +2,2 @@
 def check_smaller(test_tup1, test_tup2):
-  return all(x > y for x, y in zip(test_tup1, test_tup2))
+  return all(x >= y for x, y in zip(test_tup1, test_tup2))
```

First failing MBPP+ input:

```
input [(100, 200, 300), (100, 200, 299)]
expected False
got True
```

class: 

### Mbpp/602#arith_op (bug line 4)

Write a python function to find the first repeated character in a given string.
assert first_repeated_char("abcabc") == "a"

```diff
@@ -3,3 +3,3 @@
   for index, c in enumerate(str1):
-    if str1[:index + 1].count(c) > 1:
+    if str1[:index - 1].count(c) > 1:
       return c
```

First failing MBPP+ input:

```
input ['ABCaBC']
expected 'B'
got None
```

class: 

### Mbpp/757#off_by_one (bug line 3)

Write a function to count the pairs of reverse strings in the given string list. https://www.geeksforgeeks.org/python-program-to-count-the-pairs-of-reverse-strings/
assert count_reverse_pairs(["julia", "best", "tseb", "for", "ailuj"])== 2

```diff
@@ -2,2 +2,2 @@
 def count_reverse_pairs(test_list):
-  return sum(test_list[i+1:].count(s[::-1]) for i, s in enumerate(test_list))
+  return sum(test_list[i+1 - 1:].count(s[::-1]) for i, s in enumerate(test_list))
```

First failing MBPP+ input:

```
input [['app', '123', 'ad3', 'apple', 'elppa', 'xyx', 'bat', 'tab', 'tacocat', 'racecar', 'abc', 'zyx', 'def', 'fed']]
expected 3
got 6
```

class: 

### Mbpp/453#wrong_return (bug line 5)

Write a python function to find the sum of even factors of a number.
assert sumofFactors(18) == 26

```diff
@@ -4,3 +4,3 @@
     if (n % 2 != 0) : 
-        return 0
+        return 1
     return sum([i for i in range(2, n + 1) if n % i == 0 and i % 2 == 0])
```

First failing MBPP+ input:

```
input [101]
expected 0
got 1
```

class: 

### Mbpp/589#remove_branch (bug line 8)

Write a function to find perfect squares between two given numbers.
assert perfect_squares(1,30)==[1, 4, 9, 16, 25]

```diff
@@ -7,4 +7,2 @@
         return []
-    if a < 0:
-        a = 0
     return list(filter(lambda x: math.sqrt(x).is_integer(), range(a, b+1)))
```

First failing MBPP+ input:

```
input [0, -1]
expected [0]
got 'ValueError: math domain error'
```

class: 

### Mbpp/20#wrong_return (bug line 4)

Write a function to check if the given number is woodball or not.
assert is_woodall(383) == True

```diff
@@ -3,3 +3,3 @@
 	if not isinstance(x, int):
-		return False
+		return True
 	if x <= 0 or x % 2 == 0:
```

First failing MBPP+ input:

```
input [-43.858003490436445]
expected False
got True
```

class: 

### Mbpp/109#off_by_one (bug line 5)

Write a python function to find the number of numbers with an odd value when rotating a binary string the given number of times.
assert odd_Equivalent("011001",6) == 3

```diff
@@ -4,3 +4,3 @@
     for i in range(0,n): 
-        if (s[i] == '1'): 
+        if (s[i - 1] == '1'): 
             count = count + 1
```

First failing MBPP+ input:

```
input ['10000100110011', 5]
expected 1
got 2
```

class: 

### Mbpp/167#arith_op (bug line 3)

Write a python function to find the smallest power of 2 greater than or equal to n.
assert next_power_of_2(0) == 1

```diff
@@ -2,3 +2,3 @@
 def next_power_of_2(n): 
-  if n and not n & (n - 1):
+  if n and not n & (n + 1):
     return n
```

First failing MBPP+ input:

```
input [2]
expected 2
got 4
```

class: 

### Mbpp/639#off_by_one (bug line 3)

Write a function to sum the length of the names of a given list of names after removing the names that start with a lowercase letter.
assert sample_nam(['sally', 'Dylan', 'rebecca', 'Diana', 'Joanne', 'keith'])==16

```diff
@@ -2,3 +2,3 @@
 def sample_nam(sample_names):
-  sample_names=list(filter(lambda el:el[0].isupper() and el[1:].islower(),sample_names))
+  sample_names=list(filter(lambda el:el[0].isupper() and el[2:].islower(),sample_names))
   return len(''.join(sample_names))
```

First failing MBPP+ input:

```
input [['OOscar', 'Oscar', '$uegene', 'D@ve!', '%lice', '^ob', 'Oscar']]
expected 15
got 21
```

class: 

### Mbpp/296#off_by_one (bug line 7)

Write a python function to count inversions in an array.
assert get_Inv_Count([1,20,6,4,5]) == 5

```diff
@@ -6,3 +6,3 @@
         for j in range(i + 1, len(arr)): 
-            if (arr[i] > arr[j]): 
+            if (arr[i + 1] > arr[j]): 
                 inv_count += 1
```

First failing MBPP+ input:

```
input [[10, 9, 8, 7, 6, 5, 4, 3, 2, 1]]
expected 45
got 36
```

class: 

### Mbpp/311#remove_branch (bug line 3)

Write a python function to set the left most unset bit.
assert set_left_most_unset_bit(10) == 14

```diff
@@ -2,4 +2,2 @@
 def set_left_most_unset_bit(n): 
-    if not (n & (n + 1)): 
-        return n 
     pos, temp, count = 0, n, 0 
```

First failing MBPP+ input:

```
input [0]
expected 0
got 1
```

class: 

### Mbpp/69#arith_op (bug line 5)

Write a function to check whether a list contains the given sublist or not.
assert is_sublist([2,4,3,5,7],[3,7])==False

```diff
@@ -4,2 +4,2 @@
 		return False
-	return any(l[i:i+len(s)] == s for i in range(len(l)-len(s)+1))
+	return any(l[i:i+len(s)] == s for i in range(len(l)-len(s)-1))
```

First failing MBPP+ input:

```
input [[], []]
expected True
got False
```

class: 

### Mbpp/92#wrong_return (bug line 5)

Write a function to check whether the given number is undulating or not.
assert is_undulating(1212121) == True

```diff
@@ -4,3 +4,3 @@
 	if len(set(digits)) != 2:
-		return False
+		return True
 	return all(a != b for a, b in zip(digits, digits[1:]))
```

First failing MBPP+ input:

```
input [2121212121212119]
expected False
got True
```

class: 

### Mbpp/733#comparison_flip (bug line 5)

Write a function to find the index of the first occurrence of a given number in a sorted array.
assert find_first_occurrence([2, 5, 5, 5, 6, 6, 8, 9, 9, 9], 5) == 1

```diff
@@ -4,3 +4,3 @@
     result = -1
-    while left <= right:
+    while left < right:
         mid = (left + right) // 2
```

First failing MBPP+ input:

```
input [[5], 5]
expected 0
got -1
```

class: 

### Mbpp/433#comparison_flip (bug line 3)

Write a function to check whether the entered number is greater than the elements of the given array.
assert check_greater([1, 2, 3, 4, 5], 4) == False

```diff
@@ -2,2 +2,2 @@
 def check_greater(arr, number):
-  return all(number > el for el in arr)
+  return all(number >= el for el in arr)
```

First failing MBPP+ input:

```
input [[1, 2, 3, 4, 5], 5]
expected False
got True
```

class: 

### Mbpp/577#wrong_return (bug line 4)

Write a python function to find the last digit in factorial of a given number.
assert last_Digit_Factorial(4) == 4

```diff
@@ -3,3 +3,3 @@
     if (n == 0): 
-      return 1
+      return 0
     elif (n <= 2): 
```

First failing MBPP+ input:

```
input [0]
expected 1
got 0
```

class: 

### Mbpp/71#comparison_flip (bug line 13)

Write a function to sort a list of elements.
assert comb_sort([5, 15, 37, 25, 79]) == [5, 15, 25, 37, 79]

```diff
@@ -12,3 +12,3 @@
         for i in range(n - gap):
-            if nums[i] > nums[i + gap]:
+            if nums[i] >= nums[i + gap]:
                 nums[i], nums[i + gap] = nums[i + gap], nums[i]
```

First failing MBPP+ input:

```
(timeout)
```

class: 

### Mbpp/468#arith_op (bug line 11)

Write a function to find the maximum product formed by multiplying numbers of an increasing subsequence of that array.
assert max_product([3, 100, 4, 5, 150, 6]) == 3000

```diff
@@ -10,3 +10,3 @@
     if n > min_ending[1]:
-      min_ending = min((min_ending[0] * n, n), min_ending, key=lambda x: x[0])
+      min_ending = min((min_ending[0] // n, n), min_ending, key=lambda x: x[0])
     else:
```

First failing MBPP+ input:

```
input [[-5, -4, -3, -2, -1, 0, 1]]
expected 20
got 'ZeroDivisionError: integer division or modulo by zero'
```

class: 

### Mbpp/576#comparison_flip (bug line 5)

Write a python function to check whether a list is sublist of another or not.
assert is_Sub_Array([1,4,3,5],[1,2]) == False

```diff
@@ -4,3 +4,3 @@
     b = 0
-    while a < len(A) and b < len(B):
+    while a < len(A) and b <= len(B):
         if A[a] == B[b]:
```

First failing MBPP+ input:

```
input [[1, 2, 3], []]
expected True
got 'IndexError: list index out of range'
```

class: 

### Mbpp/435#remove_branch (bug line 3)

Write a python function to find the last digit of a given number.
assert last_Digit(123) == 3

```diff
@@ -2,4 +2,2 @@
 def last_Digit(n) :
-    if n < 0: 
-        n = -n
     return n % 10
```

First failing MBPP+ input:

```
input [-987]
expected 7
got 3
```

class: 

### Mbpp/771#bool_op (bug line 4)

Write a function to check if the given expression is balanced or not. https://www.geeksforgeeks.org/check-for-balanced-parentheses-in-an-expression/
assert check_expression("{()}[{}]") == True

```diff
@@ -3,3 +3,3 @@
 def check_expression(exp):
-    if len(exp) == 0 or len(exp) % 2 == 1:
+    if len(exp) == 0 and len(exp) % 2 == 1:
         return False
```

First failing MBPP+ input:

```
input ['']
expected False
got True
```

class: 

### Mbpp/66#comparison_flip (bug line 3)

Write a python function to count the number of positive numbers in a list.
assert pos_count([1,-2,3,-4]) == 2

```diff
@@ -2,2 +2,2 @@
 def pos_count(l):
-  return len([x for x in l if x > 0])
+  return len([x for x in l if x >= 0])
```

First failing MBPP+ input:

```
input [[0, -1, 2, -3, 4, -5, 6, -7, 8, -9, 10]]
expected 5
got 6
```

class: 

### Mbpp/741#off_by_one (bug line 3)

Write a python function to check whether all the characters are same or not.
assert all_Characters_Same("python") == False

```diff
@@ -2,2 +2,2 @@
 def all_Characters_Same(s) :
-    return all(ch == s[0] for ch in s[1:])
+    return all(ch == s[1] for ch in s[1:])
```

First failing MBPP+ input:

```
input ['ms']
expected False
got True
```

class: 

### Mbpp/264#arith_op (bug line 4)

Write a function to calculate a dog's age in dog's years.
assert dog_age(12)==61

```diff
@@ -3,3 +3,3 @@
 	if h_age <= 2:
-		d_age = h_age * 10.5
+		d_age = h_age // 10.5
 	else:
```

First failing MBPP+ input:

```
input [True]
expected 10.5
got 0.0
```

class: 

### Mbpp/803#remove_branch (bug line 3)

Write a function to check whether the given number is a perfect square or not. https://www.geeksforgeeks.org/check-if-given-number-is-perfect-square-in-cpp/
assert not is_perfect_square(10)

```diff
@@ -2,4 +2,2 @@
 def is_perfect_square(n) :
-    if n < 0:
-        return False
     return n**(1/2) == int(n**(1/2))
```

First failing MBPP+ input:

```
input [-9]
expected False
got "TypeError: int() argument must be a string, a bytes-like object or a real number, not 'complex'"
```

class: 

### Mbpp/128#comparison_flip (bug line 3)

Write a function to find words that are longer than n characters from a given list of words.
assert long_words(3,"python is a programming language")==['python','programming','language']

```diff
@@ -2,2 +2,2 @@
 def long_words(n, s):
-    return list(filter(lambda x: len(x) > n, s.split(' ')))
+    return list(filter(lambda x: len(x) >= n, s.split(' ')))
```

First failing MBPP+ input:

```
input [0, 'abc  def  ghi  jklm  nopqrs   tuvwxyz']
expected ['abc', 'def', 'ghi', 'jklm', 'nopqrs', 'tuvwxyz']
got ['abc', '', 'def', '', 'ghi', '', 'jklm', '', 'nopqrs', '', '', 'tuvwxyz']
```

class: 

### Mbpp/622#off_by_one (bug line 16)

Write a function to find the median of two sorted lists of same size.
assert get_median([1, 12, 15, 26, 38], [2, 13, 17, 30, 45], 5) == 16.0

```diff
@@ -15,3 +15,3 @@
       m1 = m2
-      m2 = arr1[0]
+      m2 = arr1[1]
       break
```

First failing MBPP+ input:

```
input [[7], [2], 1]
expected 4.5
got 'IndexError: list index out of range'
```

class: 

### Mbpp/559#off_by_one (bug line 5)

Write a function to find the sum of the largest contiguous sublist in the given list.
assert max_sub_array_sum([-2, -3, 4, -1, -2, 1, 5, -3], 8) == 7

```diff
@@ -4,3 +4,3 @@
   max_ending_here = 0
-  for i in range(0, size):
+  for i in range(0, size - 1):
     max_ending_here = max_ending_here + a[i]
```

First failing MBPP+ input:

```
input [[-1000, -900, -800, -700, -600, -500, -400, 1000, 900, 800, 700, 600, 500, 400], 14]
expected 4900
got 4500
```

class: 

### Mbpp/160#arith_op (bug line 5)

Write a function that returns integers x and y that satisfy ax + by = n as a tuple, or return None if no solution exists.
assert find_solution(2, 3, 7) == (2, 1)

```diff
@@ -4,3 +4,3 @@
 	while i * a <= n:
-		if (n - (i * a)) % b == 0: 
+		if (n - (i // a)) % b == 0: 
 			return (i, (n - (i * a)) // b)
```

First failing MBPP+ input:

```
input [7, 11, 123]
expected (5, 8)
got (14, 2)
```

class: 

### Mbpp/790#off_by_one (bug line 3)

Write a python function to check whether every even index contains even numbers of a given list.
assert even_position([3,2,1]) == False

```diff
@@ -2,2 +2,2 @@
 def even_position(nums):
-	return all(nums[i]%2==i%2 for i in range(len(nums)))
+	return all(nums[i]%2==i%2 for i in range(len(nums) - 1))
```

First failing MBPP+ input:

```
input [[2, 1, 4, 3, 6, 5, 8, 7, 10, 11, 13]]
expected False
got True
```

class: 

### Mbpp/223#wrong_return (bug line 5)

Write a function that takes in a sorted array, its length (n), and an element and returns whether the element is the majority element in the given sorted array. (The majority element is the element that occurs more than n/2 times.)
assert is_majority([1, 2, 3, 3, 3, 3, 10], 7, 3) == True

```diff
@@ -4,3 +4,3 @@
 	if x not in arr:
-		return False
+		return True
 	l = bisect_left(arr, x)
```

First failing MBPP+ input:

```
input [[], 0, 1]
expected False
got True
```

class: 

### Mbpp/113#remove_branch (bug line 7)

Write a function to check if a string represents an integer or not.
assert check_integer("python")==False

```diff
@@ -6,4 +6,2 @@
  else:
-    if text[0] in '+-':
-        text = text[1:]
     return text.isdigit()
```

First failing MBPP+ input:

```
input ['-5']
expected True
got False
```

class: 

### Mbpp/607#remove_branch (bug line 5)

Write a function to search a string for a regex pattern. The function should return the matching subtring, a start index and an end index.
assert find_literals('The quick brown fox jumps over the lazy dog.', 'fox') == ('fox', 16, 19)

```diff
@@ -4,4 +4,2 @@
   match = re.search(pattern, text)
-  if match is None:
-    return None
   s = match.start()
```

First failing MBPP+ input:

```
input ['', 'rfvPtELLC']
expected None
got "AttributeError: 'NoneType' object has no attribute 'start'"
```

class: 

### Mbpp/404#wrong_return (bug line 3)

Write a python function to find the minimum of two numbers.
assert minimum(1,2) == 1

```diff
@@ -2,2 +2,2 @@
 def minimum(a,b):   
-    return min(a,b)
+    return a
```

First failing MBPP+ input:

```
input [1000, 999]
expected 999
got 1000
```

class: 

### Mbpp/138#comparison_flip (bug line 3)

Write a python function to check whether the given number can be represented as sum of non-zero powers of 2 or not.
assert is_Sum_Of_Powers_Of_Two(10) == True

```diff
@@ -2,2 +2,2 @@
 def is_Sum_Of_Powers_Of_Two(n): 
-    return n > 0 and n % 2 == 0
+    return n >= 0 and n % 2 == 0
```

First failing MBPP+ input:

```
input [False]
expected False
got True
```

class: 

### Mbpp/6#comparison_flip (bug line 3)

Write a python function to check whether the two numbers differ at one bit position only or not.
assert differ_At_One_Bit_Pos(13,9) == True

```diff
@@ -2,3 +2,3 @@
 def is_Power_Of_Two(x: int): 
-    return x > 0 and (x & (x - 1)) == 0
+    return x >= 0 and (x & (x - 1)) == 0
 def differ_At_One_Bit_Pos(a: int,b: int):
```

First failing MBPP+ input:

```
input [0, 0]
expected False
got True
```

class: 

### Mbpp/244#wrong_return (bug line 5)

Write a python function to find the next perfect square greater than a given number.
assert next_Perfect_Square(35) == 36

```diff
@@ -4,3 +4,3 @@
     if N < 0:
-        return 0
+        return 1
     nextN = math.floor(math.sqrt(N)) + 1
```

First failing MBPP+ input:

```
input [-5]
expected 0
got 1
```

class: 

### Mbpp/755#comparison_flip (bug line 4)

Write a function to find the second smallest number in a list.
assert second_smallest([1, 2, -8, -2, 0, -2])==-2

```diff
@@ -3,3 +3,3 @@
   sorted_set = sorted(set(numbers))
-  if len(sorted_set) < 2:
+  if len(sorted_set) <= 2:
     return None
```

First failing MBPP+ input:

```
input [[1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2]]
expected 2
got None
```

class: 

### Mbpp/247#off_by_one (bug line 12)

Write a function to find the length of the longest palindromic subsequence in the given string.
assert lps("TENS FOR TENS") == 5

```diff
@@ -11,2 +11,2 @@
 				dp[i][j] = max(dp[i + 1][j], dp[i][j - 1])
-	return dp[0][n - 1]
+	return dp[1][n - 1]
```

First failing MBPP+ input:

```
input ['AAAAAAA']
expected 7
got 6
```

class: 
