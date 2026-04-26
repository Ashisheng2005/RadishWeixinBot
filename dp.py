"""
题目：爬楼梯（LeetCode 70）
假设你正在爬楼梯。需要 n 阶你才能到达楼顶。
每次你可以爬 1 或 2 个台阶。你有多少种不同的方法可以爬到楼顶呢？

动态规划思路：
定义 dp[i] 为爬到第 i 阶的方法数，则 dp[i] = dp[i-1] + dp[i-2]
初始条件：dp[0] = 1, dp[1] = 1
"""

def climb_stairs(n: int) -> int:
    """使用动态规划计算爬楼梯的方法数"""
    if n <= 1:
        return 1
    dp = [0] * (n + 1)
    dp[0] = 1
    dp[1] = 1
    for i in range(2, n + 1):
        dp[i] = dp[i - 1] + dp[i - 2]
    return dp[n]

if __name__ == "__main__":
    n = 10
    result = climb_stairs(n)
    print(f"爬 {n} 阶楼梯的不同方法数: {result}")
