from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    UpdateView,
)
from django.views.generic.detail import SingleObjectMixin

from .forms import CommentForm, PostCreateForm
from .models import Category, Comment, Post


class PostListView(ListView):
    model = Post
    template_name = "blog/index.html"
    context_object_name = "post_list"
    paginate_by = 10
    ordering = "-pub_date"

    def get_queryset(self):
        return Post.published(False).order_by(*Post._meta.ordering)


class CategoryListView(ListView):
    model = Post
    template_name = "blog/category.html"
    context_object_name = "posts"
    paginate_by = 10
    ordering = "-pub_date"

    def dispatch(self, request, *args, **kwargs):
        self.category = get_object_or_404(Category, slug=kwargs["category_slug"])
        if not self.category.is_published:
            raise Http404("Категория не найдена или была снята с публикации.")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Post.published(False).order_by(*Post._meta.ordering)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["category"] = self.category
        return context


class PostDetailView(DetailView):
    model = Post
    template_name = "blog/detail.html"

    def get_object(self, queryset=None):
        post = get_object_or_404(Post, id=self.kwargs['post_id'])

        is_author = self.request.user == post.author

        if not post.is_published and not is_author:
            raise Http404("Публикация не найдена.")

        if post.is_published:
            return post

        return get_object_or_404(Post.published(True), id=self.kwargs['post_id'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = CommentForm()
        context["comments"] = self.object.comments.select_related("author")
        context["post"] = self.object
        context["comment_count"] = self.object.comments.count()
        return context


class UserDetailView(DetailView):
    model = User
    template_name = "blog/profile.html"
    context_object_name = "profile"
    paginate_by = 10
    ordering = "-pub_date"

    def get_object(self, queryset=None):
        username = self.kwargs.get("username")
        return get_object_or_404(User, username=username)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.get_object()

        if self.request.user == user:
            posts = Post.published(True) \
                .filter(author=user).order_by(*Post._meta.ordering)
        else:
            posts = Post.published(False) \
                .order_by(*Post._meta.ordering)

        paginator = Paginator(posts, self.paginate_by)
        page_number = self.request.GET.get("page")
        context["page_obj"] = paginator.get_page(page_number)
        return context


class PostCreateView(LoginRequiredMixin, CreateView):
    form_class = PostCreateForm
    template_name = "blog/create.html"
    login_url = reverse_lazy("login")

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy(
            "blog:profile",
            kwargs={"username": self.request.user.username}
        )


class PostUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Post
    form_class = PostCreateForm
    template_name = "blog/create.html"

    def test_func(self):
        return self.get_object().author == self.request.user

    def handle_no_permission(self):
        return redirect(
            reverse("blog:post_detail", kwargs={"post_id": self.get_object().id})
        )

    def get_success_url(self):
        return reverse_lazy("blog:post_detail", kwargs={"post_id": self.object.id})


class PostDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Post
    template_name = "blog/create.html"
    success_url = reverse_lazy("blog:index")

    def test_func(self):
        return self.get_object().author == self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = PostCreateForm(
            instance=self.get_object()
        )
        return context


class UserUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    fields = ["first_name", "last_name", "username", "email"]
    template_name = "blog/user.html"

    def get_object(self, queryset=None):
        return self.request.user

    def get_success_url(self):
        return reverse_lazy(
            "blog:profile",
            kwargs={"username": self.request.user.username}
        )


class CommentCreateView(LoginRequiredMixin, SingleObjectMixin, FormView):
    template_name = "blog/detail.html"
    form_class = CommentForm
    model = Post

    def get_object(self, queryset=None):
        return get_object_or_404(Post, id=self.kwargs['post_id'])

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        comment = form.save(commit=False)
        comment.author = self.request.user
        comment.post = self.object
        comment.save()
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("blog:post_detail", kwargs={"post_id": self.object.pk})


class CommentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Comment
    form_class = CommentForm
    template_name = "blog/comment.html"

    def test_func(self):
        return self.get_object().author == self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["comment"] = self.get_object()
        return context

    def get_object(self, queryset=None):
        return get_object_or_404(Comment, id=self.kwargs['comment_id'])

    def get_success_url(self):
        return reverse("blog:post_detail", kwargs={"post_id": self.object.post.pk})


class CommentDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Comment
    template_name = 'blog/comment.html'

    def test_func(self):
        return self.get_object().author == self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['comment'] = self.get_object()
        return context

    def get_object(self, queryset=None):
        return get_object_or_404(Comment, id=self.kwargs['comment_id'])

    def get_success_url(self):
        return reverse_lazy(
            'blog:post_detail',
            kwargs={'post_id': self.object.post.pk}
        )
